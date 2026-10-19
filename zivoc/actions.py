import re
import secrets
from datetime import datetime

from flask import current_app, request, session

from . import catalog as erp
from . import config, db
from .core import AppError, Redirect, files, filter_int, hash_equals, hash_password, is_numeric, now, php_round, post, random_hex, today, utf8_len, verify_password
from .helpers import csrf_token, next_stage, owner, positive, privileged, redirect, require_admin, required, salesman, to_int, user, val, reset_user_cache
from .hr import hr_action, hr_lock
from .leads import lead_create, lead_update
from .team import sync_team
from .quotations import qt_action
from .uploads import image_info, read_upload
from .workflow import wf_action, wf_production_gate, wf_survey

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
SAVE_FORM_ACTIONS = ('wf_survey', 'wf_quote', 'qt_create', 'lead', 'lead_update')
PAGES = ('home', 'leads', 'lead_create', 'orders', 'order', 'products', 'profile', 'team', 'attendance', 'commissions', 'reminders', 'calendar',
         'salary', 'checkout', 'quotations', 'quotation_create', 'quote_templates')
MONTH_RE = re.compile(r'^20[0-9]{2}-(0[1-9]|1[0-2])$')


def client_ip():
    return (request.remote_addr or 'unknown')[:64]


def _login():
    ip = client_ip()
    if int(db.one('SELECT COUNT(*) n FROM login_attempts WHERE ip=%s AND attempted_at > DATE_SUB(NOW(), INTERVAL 15 MINUTE)', [ip])['n']) >= 10:
        raise AppError('Too many attempts. Try again in 15 minutes.')
    db.q('INSERT INTO login_attempts(ip) VALUES (%s)', [ip])
    login = required('login', 190)
    account = db.one('SELECT * FROM users WHERE (username=%s OR email=%s) AND active=1', [login, login])
    if not account:
        sync_team(force=False)
        account = db.one('SELECT * FROM users WHERE (username=%s OR email=%s) AND active=1', [login, login])
    if not account or not verify_password(val('password'), account['password']):
        raise AppError('Username / email or password is incorrect.')
    db.q('DELETE FROM login_attempts WHERE ip=%s', [ip])
    session.regenerate()
    session['uid'] = account['id']
    session['csrf'] = random_hex(32)
    reset_user_cache()
    redirect('/')


def _lead_status(u):
    record = owner('leads', to_int(val('id')), u)
    status = val('status')
    if status not in ('new', 'contacted', 'qualified', 'lost') or record['status'] == 'converted':
        raise AppError('Invalid lead status.')
    db.q('UPDATE leads SET status=%s WHERE id=%s', [status, record['id']])


def _order(u):
    if u['role'] == 'finance':
        raise AppError('Sales or admin access required to create orders.')
    lead_id = to_int(val('lead_id'))
    lead = owner('leads', lead_id, u) if lead_id else None
    sid = int(lead['salesman_id']) if lead else salesman(u)
    selected = post().get('items', {})
    if not isinstance(selected, dict) or not selected or len(selected) > 100:
        raise AppError('Select between 1 and 100 products.')
    catalog = erp.catalog()
    checked = []
    total = 0
    for code, qty in selected.items():
        qty = filter_int(qty)
        if code not in catalog or not qty or qty < 1 or qty > 10000:
            raise AppError('Invalid product or quantity.')
        checked.append((catalog[code], qty))
        total += float(catalog[code]['price']) * qty
    if total > 999999999:
        raise AppError('Order total exceeds limit.')
    customer = lead['name'] if lead else required('customer', 150)
    phone = lead['phone'] if lead else required('phone', 30)
    address = lead['address'] if lead else required('address', 3000)
    lines = [(erp.local_product(item), qty, float(item['price'])) for item, qty in checked]
    rate = db.one('SELECT commission_rate FROM users WHERE id=%s', [sid])['commission_rate']
    db.begin()
    if not lead:
        db.q("INSERT INTO leads(salesman_id,name,phone,address,status) VALUES (%s,%s,%s,%s,'converted')", [sid, customer, phone, address])
        lead_id = int(db.insert_id())
    db.q("INSERT INTO orders(salesman_id,lead_id,customer,phone,address,source,total,commission_rate,stage) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'order')",
         [sid, lead_id, customer, phone, address, u['role'], total, rate])
    oid = int(db.insert_id())
    for product_id, qty, price in lines:
        db.q('INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES (%s,%s,%s,%s)', [oid, product_id, qty, price])
    db.q('INSERT INTO wf_surveys(order_id,updated_by) VALUES (%s,%s)', [oid, u['id']])
    db.q("INSERT INTO order_history(order_id,actor_id,stage,note) VALUES (%s,%s,'survey','Customer and products saved. Survey pending.')", [oid, u['id']])
    if lead:
        db.q("UPDATE leads SET status='converted' WHERE id=%s", [lead_id])
    db.commit()
    session['flash'] = 'Customer and products saved. Continue with survey, drawing and quotation.'
    redirect('/?page=order&id=%d' % oid)


def _stage(u):
    db.begin()
    record = db.one('SELECT * FROM orders WHERE id=%s FOR UPDATE', [to_int(val('id'))])
    if not record or (not privileged(u) and int(record['salesman_id']) != int(u['id'])):
        raise AppError('Order unavailable.')
    wf_production_gate(record)
    target = 'production' if wf_survey(int(record['id'])) else next_stage(record['stage'])
    if not target:
        raise AppError('Order is already in production.')
    if target in ('verified', 'production') and not privileged(u):
        raise AppError('Finance or admin approval required.')
    if u['role'] == 'finance' and target not in ('verified', 'production'):
        raise AppError('Only finance approval and production release are available to finance.')
    survey = val('survey')
    advance = record['advance']
    note = required('note', 2000)
    if target == 'advance' and survey == '':
        raise AppError('Record door dimensions and survey details first.')
    if target == 'finance':
        advance = positive('advance')
        if advance > float(record['total']):
            raise AppError('Advance cannot exceed order total.')
    db.q("UPDATE orders SET stage=%s, advance=%s, survey=COALESCE(NULLIF(%s,''),survey) WHERE id=%s", [target, advance, survey, record['id']])
    db.q('INSERT INTO order_history(order_id,actor_id,stage,note) VALUES (%s,%s,%s,%s)', [record['id'], u['id'], target, note])
    if target == 'production':
        db.q('INSERT IGNORE INTO commissions(order_id,salesman_id,amount) VALUES (%s,%s,%s)',
             [record['id'], record['salesman_id'], php_round(float(record['total']) * float(record['commission_rate']) / 100, 2)])
    db.commit()


def _reminder(u):
    order_id = to_int(val('order_id'))
    lead_id = to_int(val('lead_id'))
    sid = int(u['id'])
    if order_id:
        sid = int(owner('orders', order_id, u)['salesman_id'])
    if lead_id:
        lead = owner('leads', lead_id, u)
        if order_id and sid != int(lead['salesman_id']):
            raise AppError('Record owners do not match.')
        sid = int(lead['salesman_id'])
    text = val('due_at')
    try:
        date = datetime.strptime(text, '%Y-%m-%dT%H:%M')
    except ValueError:
        date = None
    if date is None or date.strftime('%Y-%m-%dT%H:%M') != text:
        raise AppError('Enter a valid reminder date and time.')
    db.q('INSERT INTO reminders(salesman_id,order_id,lead_id,title,due_at) VALUES (%s,%s,%s,%s,%s)',
         [sid, order_id or None, lead_id or None, required('title', 200), date.strftime('%Y-%m-%d %H:%M:%S')])


def _team_sync(u):
    require_admin(u)
    result = sync_team(force=True)
    if result['error']:
        raise AppError(result['error'])
    session['flash'] = 'ERP sync complete: %d added, %d updated.' % (result['added'], result['updated'])



def _user_update(u):
    require_admin(u)
    user_id = to_int(val('id'))
    record = db.one('SELECT * FROM users WHERE id=%s', [user_id])
    if not record or record['role'] not in ('salesman', 'freelancer'):
        raise AppError('Sales member unavailable.')
    rate = positive('commission_rate', True)
    if rate > 100:
        raise AppError('Invalid percentage.')
    db.q('UPDATE users SET monthly_target=%s,commission_rate=%s,active=%s WHERE id=%s',
         [positive('monthly_target', True), rate, 1 if val('active') == '1' else 0, user_id])


def _paid(u):
    if not privileged(u):
        raise AppError('Finance access required.')
    db.q('UPDATE commissions SET paid_at=NOW(),payment_reference=%s WHERE id=%s AND paid_at IS NULL', [required('payment_reference', 190), to_int(val('id'))])


def _password(u):
    if not verify_password(val('current_password'), u['password']):
        raise AppError('Current password is incorrect.')
    new = required('password')
    if utf8_len(new) < 12:
        raise AppError('Use at least 12 characters.')
    db.q('UPDATE users SET password=%s WHERE id=%s', [hash_password(new), u['id']])
    session.regenerate()


def _attendance(u):
    db.begin()
    hr_lock(int(u['id']))
    if db.one("SELECT id FROM leave_requests WHERE user_id=%s AND status='approved' AND start_date<=%s AND end_date>=%s", [u['id'], today(), today()]):
        raise AppError('You have approved leave today. Contact admin before checking in.')
    lat, lon, acc = val('latitude'), val('longitude'), val('accuracy')
    if not is_numeric(lat) or not is_numeric(lon) or not is_numeric(acc) or abs(float(lat)) > 90 or abs(float(lon)) > 180 or float(acc) < 0:
        raise AppError('Valid GPS location is required.')
    upload = files().get('selfie')
    limit = 5 * 1024 * 1024
    data = read_upload(upload, limit)
    if data is None or not data or len(data) > limit:
        raise AppError('Capture a selfie below 5 MB.')
    info = image_info(data)
    if not info or info[0] not in ('image/jpeg', 'image/png', 'image/webp') or info[1] > 6000 or info[2] > 6000:
        raise AppError('Use a valid JPG, PNG or WebP selfie.')
    name = secrets.token_hex(24) + '.' + {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}[info[0]]
    config.SELFIE_DIR.mkdir(parents=True, exist_ok=True)
    path = config.SELFIE_DIR / name
    try:
        with open(path, 'wb') as handle:
            handle.write(data)
    except OSError:
        raise AppError('Unable to save selfie.')
    try:
        db.q('INSERT INTO attendance(user_id,day,punched_at,latitude,longitude,accuracy,selfie) VALUES (%s,%s,%s,%s,%s,%s,%s)',
             [u['id'], today(), now().strftime('%Y-%m-%d %H:%M:%S'), lat, lon, acc, name])
        db.commit()
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _product_price(u):
    if u['role'] != 'admin':
        raise AppError('Admin access required.')
    code = required('item_code', 190)
    raw = val('price')
    if not is_numeric(raw) or float(raw) < 0 or float(raw) > 99999999:
        raise AppError('Enter a valid price.')
    if code not in erp.catalog():
        raise AppError('Product not found.')
    erp.set_price(code, round(float(raw), 2))


SIMPLE_ACTIONS = {
    'product_price': _product_price,
    'lead': lead_create,
    'lead_update': lead_update,
    'lead_status': _lead_status,
    'order': _order,
    'stage': _stage,
    'reminder': _reminder,
    'team_sync': _team_sync,
    'user_update': _user_update,
    'paid': _paid,
    'password': _password,
    'attendance': _attendance,
}


def _mark_done(u):
    record = owner('reminders', to_int(val('id')), u)
    db.q('UPDATE reminders SET done=1 WHERE id=%s', [record['id']])


SIMPLE_ACTIONS['done'] = _mark_done


def _dispatch(action, u):
    if action == 'login':
        _login()
    if not u:
        raise AppError('Please sign in.')
    if u['role'] == 'freelancer' and action in ('attendance', 'leave_request', 'workdays'):
        raise AppError('Attendance is not available for freelancers.')
    if qt_action(action, u) or wf_action(action, u) or hr_action(action, u):
        session['flash'] = 'Saved successfully.'
        return
    if action == 'logout':
        session.destroy()
        redirect('/')
    if action in ('product', 'product_update'):
        raise AppError('Products are managed by the ERP API.')
    handler = SIMPLE_ACTIONS.get(action)
    if handler is None:
        raise AppError('Unknown action.')
    handler(u)


def handle_post():
    valid_csrf = False
    action = ''
    try:
        if not hash_equals(csrf_token(), post().get('csrf', '')):
            raise AppError('Session expired. Reload and try again.')
        valid_csrf = True
        action = val('action')
        _dispatch(action, user())
        if action in SAVE_FORM_ACTIONS:
            session.pop('save_form', None)
        session['flash'] = 'Saved successfully.'
    except Redirect:
        raise
    except Exception as exc:
        if valid_csrf and action in SAVE_FORM_ACTIONS:
            saved = dict(post())
            saved.pop('csrf', None)
            session['save_form'] = saved
        try:
            db.rollback()
        except Exception:
            pass
        if isinstance(exc, db.MySQLError):
            reference = secrets.token_hex(4)
            current_app.logger.error('Save reference %s action %s: %r', reference, action or 'unknown', exc)
            if exc.args and exc.args[0] == 1062:
                session['error'] = 'This record already exists (daily attendance, email or order reference).'
            else:
                session['error'] = 'Database save failed (reference %s). Apply quotation-update.sql, then retry; entered values have been retained.' % reference
        elif isinstance(exc, AppError):
            session['error'] = str(exc)
        else:
            current_app.logger.exception('Unhandled error in action %s', action or 'unknown')
            session['error'] = 'The request could not be completed. Check the server log.'
    created = session.pop('quote_created_order', None)
    if created is not None:
        created = int(created)
        quote = db.one('SELECT id FROM wf_quotations WHERE order_id=%s', [created])
        if val_safe('print_after') == '1' and quote:
            return redirect_response('/workflow-file?quotation=%d' % int(quote['id']))
        return redirect_response('/?page=order&id=%d#wf-quotation' % created)
    page = request.args.get('page', 'home')
    if action in ('lead', 'lead_update') and 'error' not in session:
        page = 'leads'
    if page not in PAGES:
        page = 'home'
    context = ''
    if 'employee_id' in request.args:
        context += '&employee_id=%d' % to_int(request.args.get('employee_id'))
    month = request.args.get('month', '')
    if month and MONTH_RE.match(month):
        from urllib.parse import quote as urlquote
        context += '&month=' + urlquote(month, safe='')
    target = '/?page=' + page + context
    if 'id' in request.args:
        target += '&id=%d' % to_int(request.args.get('id'))
    return redirect_response(target)


def val_safe(key):
    try:
        return val(key)
    except AppError:
        return ''


def redirect_response(location):
    from flask import redirect as flask_redirect
    return flask_redirect(location, 303)
