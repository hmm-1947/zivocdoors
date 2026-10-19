import json
import re

import requests

from . import config, db


def _connection():
    if config.POS_DB_NAME:
        return db.connect(config.POS_DB_HOST, None, config.POS_DB_USER, config.POS_DB_PASSWORD, config.POS_DB_NAME), True
    return db.conn(), False


def sync_employees():
    token = config.POS_ERP_TOKEN or config.ERP_TOKEN
    default_password = config.POS_DEFAULT_PASSWORD_HASH
    if not token or not default_password:
        return {'success': False, 'message': 'ERPNext token and default password hash must be configured'}, 500
    fields = ['name', 'employee_name', 'status', 'department', 'employment_type', 'designation', 'cell_number', 'prefered_email']
    try:
        response = requests.get(
            config.ERP_BASE_URL + '/api/resource/Employee',
            params={'fields': json.dumps(fields), 'limit_page_length': 1000},
            headers={'Authorization': 'token ' + token, 'Accept': 'application/json'},
            timeout=(10, 30),
        )
    except requests.RequestException as exc:
        return {'success': False, 'message': 'ERPNext API connection failed', 'error': str(exc)}, 500
    if response.status_code != 200:
        return {'success': False, 'message': 'ERPNext API request failed', 'http_code': response.status_code, 'response': response.text}, response.status_code
    try:
        data = response.json()
    except ValueError as exc:
        return {'success': False, 'message': 'Invalid JSON received from ERPNext', 'error': str(exc)}, 500
    if not isinstance(data, dict) or not isinstance(data.get('data'), list):
        return {'success': False, 'message': 'Employee data not found in ERPNext response'}, 500
    connection, owned = _connection()
    inserted = updated = skipped = 0
    errors = []
    processed = []
    try:
        for employee in data['data']:
            name = str(employee.get('employee_name') or '').strip()
            mobile = str(employee.get('cell_number') or '').strip()
            email = str(employee.get('prefered_email') or '').strip()
            employment = str(employee.get('employment_type') or '').strip()
            role = employment.lower() if employment else 'employee'
            status = str(employee.get('status') or '').strip()
            if mobile == '':
                skipped += 1
                errors.append({'employee': name, 'employment_type': employment, 'role': role, 'reason': 'Mobile number is empty'})
                continue
            mobile = re.sub(r'[^0-9]', '', mobile)
            if mobile == '':
                skipped += 1
                errors.append({'employee': name, 'employment_type': employment, 'role': role, 'reason': 'Invalid mobile number'})
                continue
            if name == '':
                name = mobile
            if email == '':
                email = mobile + '@employee.zivoc.invalid'
            email = email.lower()
            active = 1 if status.lower() == 'active' else 0
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT id FROM users WHERE username=%s LIMIT 1', (mobile,))
                    exists = cursor.fetchone() is not None
                    if exists:
                        cursor.execute('UPDATE users SET name=%s,email=%s,password=%s,role=%s,active=%s WHERE username=%s',
                                       (name, email, default_password, role, active, mobile))
                        updated += 1
                    else:
                        cursor.execute(
                            'INSERT INTO users(name,username,email,password,role,monthly_target,commission_rate,active) VALUES (%s,%s,%s,%s,%s,0.00,0.00,%s)',
                            (name, mobile, email, default_password, role, active))
                        inserted += 1
                processed.append({'name': name, 'username': mobile, 'email': email, 'employment_type': employment, 'role': role, 'active': active,
                                  'action': 'updated' if exists else 'inserted'})
            except db.MySQLError as exc:
                errors.append({'employee': name, 'username': mobile, 'employment_type': employment, 'role': role, 'reason': str(exc)})
    finally:
        if owned:
            connection.close()
    return {
        'success': True,
        'message': 'All employees synchronized successfully. Employment Type saved to SQL role.',
        'fetched': len(data['data']),
        'inserted': inserted,
        'updated': updated,
        'skipped': skipped,
        'employees': processed,
        'errors': errors,
    }, 200
