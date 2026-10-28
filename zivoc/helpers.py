import re

from flask import g, session
from markupsafe import Markup, escape

from . import db
from .core import AppError, Redirect, hash_equals, is_numeric, php_round, post, random_hex, utf8_len

STAGES = {
    'order': 'Order received',
    'site_visit': 'Site visit',
    'survey': 'Door survey',
    'advance': 'Collect advance',
    'finance': 'Finance review',
    'verified': 'Finance approved',
    'production': 'In production',
}


def user():
    if 'user_loaded' in g:
        return g.user_value
    account = None
    uid = session.get('uid')
    if uid:
        account = db.one('SELECT * FROM users WHERE id=%s AND active=1', [uid])
    g.user_loaded = True
    g.user_value = account
    return account


def reset_user_cache():
    g.pop('user_loaded', None)
    g.pop('user_value', None)


def privileged(u):
    return u['role'] in ('admin', 'finance')


def require_admin(u):
    if u['role'] != 'admin':
        raise AppError('Administrator access required.')


def redirect(location):
    raise Redirect(location)


def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = random_hex(32)
    return session['csrf']


def csrf_field():
    return Markup('<input type="hidden" name="csrf" value="%s">') % csrf_token()


def val(key, maximum=5000):
    raw = post().get(key, '')
    value = raw.strip() if isinstance(raw, str) else ('Array' if isinstance(raw, dict) else str(raw).strip())
    if utf8_len(value) > maximum:
        raise AppError('Input is too long.')
    return value


def required(key, maximum=190):
    value = val(key, maximum)
    if value == '':
        raise AppError(key.replace('_', ' ').capitalize() + ' is required.')
    return value


def positive(key, zero=False):
    text = required(key)
    if not is_numeric(text):
        raise AppError('Enter a valid ' + key + '.')
    number = float(text)
    if number != number or number in (float('inf'), float('-inf')) or number < (0 if zero else 0.01) or number > 999999999:
        raise AppError('Enter a valid ' + key + '.')
    return php_round(number, 2)


def owner(table, record_id, u):
    if table not in ('orders', 'leads', 'reminders'):
        raise AppError('Invalid record.')
    record = db.one('SELECT * FROM ' + table + ' WHERE id=%s', [record_id])
    if not record or (not privileged(u) and int(record['salesman_id']) != int(u['id'])):
        raise AppError('Record unavailable.')
    return record


def salesman(u):
    if not privileged(u):
        return int(u['id'])
    sid = to_int(val("salesman_id"))
    if not db.one("SELECT id FROM users WHERE id=%s AND role IN ('salesman','freelancer') AND active=1", [sid]):
        raise AppError('Select an active salesman or freelancer.')
    return sid


def to_int(value, default=0):
    match = re.match(r'\s*([+-]?\d+)', str(value if value is not None else ''))
    return int(match.group(1)) if match else default


def next_stage(stage):
    return {
        'order': 'site_visit',
        'site_visit': 'survey',
        'survey': 'advance',
        'advance': 'finance',
        'finance': 'production',
        'verified': 'production',
    }.get(stage)


def cm_text(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return '' if value is None else value
    return '%g' % round(number / 10, 3)


def cm_unit(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return '' if value is None else value
    return '%g cm' % round(number / 10, 3)


def dim_unit(value, unit='cm'):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return '' if value is None else value
    if unit == 'in':
        return '%g in' % round(number / 25.4, 2)
    return '%g cm' % round(number / 10, 3)
