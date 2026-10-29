import json
import re
import threading
import time

import requests

from . import config, db
from . import avatars
from .core import hash_password


DEFAULT_PASSWORD = 'Apple@123'
ROLE_MAP = {'salesman': 'salesman', 'freelancer': 'freelancer', 'fabricator': 'fabricator', 'dsh-finance': 'finance', 'dsh-admin': 'admin'}
_state = {'last': 0.0}
_lock = threading.Lock()


def _clean_email(*values):
    for value in values:
        text = str(value or '').strip().lower()
        if re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', text):
            return text[:190]
    return ''


def _fetch():
    token = config.ERP_TOKEN
    if not token:
        return None, 'ERP token is not configured.'
    fields = ['name', 'employee_name', 'employment_type', 'status', 'company_email', 'personal_email', 'prefered_email', 'cell_number', 'image']
    try:
        response = requests.get(config.ERP_BASE_URL + '/api/resource/Employee', params={'fields': json.dumps(fields), 'limit_page_length': 5000},
                                headers={'Authorization': 'token ' + token, 'Accept': 'application/json'}, timeout=(10, 30))
        data = response.json()
    except (requests.RequestException, ValueError):
        return None, 'Employees could not be loaded from ERP.'
    if response.status_code != 200 or not isinstance(data, dict) or not isinstance(data.get('data'), list):
        return None, 'Employees could not be loaded from ERP.'
    return data['data'], ''


def _sync_avatar(code, item):
    try:
        record = db.one('SELECT * FROM users WHERE employee_id=%s', [code])
        if record:
            avatars.pull(record, item.get('image'))
    except Exception:
        pass


def sync_team(force=True):
    with _lock:
        if not force and time.time() - _state['last'] < 60:
            return {'added': 0, 'updated': 0, 'error': ''}
        _state['last'] = time.time()
        employees, error = _fetch()
        if employees is None:
            return {'added': 0, 'updated': 0, 'error': error}
        added = updated = 0
        default_hash = None
        for item in employees:
            role = ROLE_MAP.get(str(item.get('employment_type') or '').strip().lower())
            code = str(item.get('name') or '').strip()[:60]
            if not role or not code:
                continue
            name = (str(item.get('employee_name') or '').strip() or code)[:120]
            mobile = re.sub(r'[^0-9]', '', str(item.get('cell_number') or ''))[:30]
            username = (mobile or code.lower().replace(' ', '-'))[:80]
            active = 1 if str(item.get('status') or '').strip().lower() == 'active' else 0
            email = _clean_email(item.get('company_email'), item.get('personal_email'), item.get('prefered_email'))
            record = db.one('SELECT * FROM users WHERE employee_id=%s', [code]) or db.one('SELECT * FROM users WHERE username=%s', [username])
            if email:
                taken = db.one('SELECT id FROM users WHERE email=%s', [email])
                if taken and (not record or int(taken['id']) != int(record['id'])):
                    email = ''
            if not email:
                email = username + '@employee.zivoc.invalid'
            if record:
                db.q('UPDATE users SET employee_id=%s,name=%s,role=%s' + (',active=0' if not active else '') + ' WHERE id=%s', [code, name, role, record['id']])
                updated += 1
                _sync_avatar(code, item)
            else:
                if default_hash is None:
                    default_hash = hash_password(DEFAULT_PASSWORD)
                db.q('INSERT INTO users(name,username,email,password,role,monthly_target,commission_rate,active,employee_id) VALUES (%s,%s,%s,%s,%s,0,0,%s,%s)',
                     [name, username, email, default_hash, role, active, code])
                added += 1
                _sync_avatar(code, item)
        return {'added': added, 'updated': updated, 'error': ''}
