import csv
import hmac
import io
import json
import re
import secrets
from urllib.parse import urlencode

from flask import Response, abort, current_app, jsonify, render_template, request, send_file, session

from . import actions, catalog as erp, config, db, schema
from .core import (AppError, Redirect, add_days, add_months, fnum, hash_equals, hash_password, is_numeric, money, now, php_date, php_round, post,
                   random_hex, today, to_dt, verify_password)
from .deletion import log_listing
from .doorhandles import dh_brands
from .drawing import wf_drawing_svg
from .helpers import STAGES, cm_text, cm_unit, dim_unit, csrf_token, next_stage, owner, privileged, redirect, reset_user_cache, to_int, user
from .hr import hr_advance_total, hr_attendance, hr_employee, hr_month, hr_workdays
from .leads import lead_form_values, lead_listing, party_people
from .avatars import refresh as avatar_refresh
from .team import sync_team

from .quotations import qt_failed_form, qt_listing, qt_quote_rows
from .workflow import (WF_MEASURES, wf_can_edit, wf_date, wf_items, wf_label, wf_latest_drawing, wf_measurements, wf_quote_number, wf_quote_status,
                       wf_ready, wf_survey)

ALLOWED_PAGES = ('home', 'leads', 'lead_create', 'orders', 'order', 'products', 'profile', 'team', 'attendance', 'commissions', 'reminders', 'checkout',
                 'calendar', 'salary', 'quotations', 'quotation_create', 'quote_templates', 'survey', 'order_forms', 'door_handles', 'commission_schemes', 'deletion_logs')
NAV = (('home', 'Overview'), ('leads', 'Leads'), ('orders', 'My Orders'), ('quotations', 'Quotation Details'),
       ('products', 'Products'), ('reminders', 'Follow-ups'), ('attendance', 'Attendance'), ('salary', 'Salary & advances'), ('commissions', 'Wallet'))
FREELANCER_HIDDEN = ('attendance', 'calendar')
BOTTOM_NAV = (('home', 'Home'), ('leads', 'Leads'), ('quotation_create', 'Quotation'), ('orders', 'My Orders'), ('commissions', 'Wallet'))


def scope(all_access, u, column='salesman_id'):
    return '1=1' if all_access else '%s=%d' % (column, int(u['id']))


def positive_value(value):
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def has_commission(oid):
    return bool(db.one('SELECT id FROM commissions WHERE order_id=%s', [oid]))


def wf_attachments(oid, kind):
    return db.rows('SELECT * FROM wf_attachments WHERE order_id=%s AND kind=%s ORDER BY id DESC', [oid, kind])


def wf_drawing_options(oid):
    return db.rows('SELECT id,measurement_id,revision FROM wf_drawings WHERE order_id=%s ORDER BY id DESC', [oid])


def json_obj(text):
    try:
        data = json.loads(text) if text else None
    except ValueError:
        data = None
    return data if isinstance(data, dict) else {}



def ctx_home(u, all_access, reminders):
    first = php_date('Y-m-01')
    nxt = add_months(first, 1).strftime('%Y-%m-%d')
    where = scope(all_access, u)
    order_scope = '1=1' if all_access else 'o.salesman_id=%d' % int(u['id'])
    exists = ("EXISTS(SELECT 1 FROM order_history h WHERE h.order_id=o.id AND h.stage IN ('verified','production') AND h.created_at>=%s AND h.created_at<%s)")
    approved = float(db.one('SELECT COALESCE(SUM(o.total),0) n FROM orders o JOIN commissions c ON c.order_id=o.id WHERE ' + order_scope + ' AND ' + exists,
                            [first, nxt])['n'])
    earned = float(db.one('SELECT COALESCE(SUM(c.amount),0) n FROM commissions c JOIN orders o ON o.id=c.order_id WHERE ' +
                          ('1=1' if all_access else 'c.salesman_id=%d' % int(u['id'])) + ' AND ' + exists, [first, nxt])['n'])
    if all_access:
        target = float(db.one("SELECT COALESCE(SUM(monthly_target),0) n FROM users WHERE role IN ('salesman','freelancer','fabricator') AND active=1")['n'])
    else:
        target = float(u['monthly_target'])
    pct = int(min(100, php_round(approved / target * 100))) if target > 0 else 0
    punch = db.one('SELECT * FROM attendance WHERE user_id=%s AND day=%s', [u['id'], today()])
    lead_scope = where
    quote_scope = '1=1' if all_access else 'o.salesman_id=%d' % int(u['id'])
    monthly_leads = int(db.one('SELECT COUNT(*) n FROM leads WHERE ' + lead_scope + ' AND created_at>=%s AND created_at<%s', [first, nxt])['n'])
    total_leads = int(db.one('SELECT COUNT(*) n FROM leads WHERE ' + lead_scope)['n'])
    stats = db.one(
        "SELECT COUNT(*) total,COALESCE(SUM(q.quote_date>=%s AND q.quote_date<%s),0) monthly,COALESCE(SUM(q.status='approved'),0) won,"
        "COALESCE(SUM(q.status='approved' AND q.quote_date>=%s AND q.quote_date<%s),0) monthly_won "
        'FROM wf_quotations q JOIN orders o ON o.id=q.order_id WHERE ' + quote_scope, [first, nxt, first, nxt])
    confirmed = db.one("SELECT COUNT(*) total,COALESCE(SUM(created_at>=%s AND created_at<%s),0) monthly FROM orders WHERE " + lead_scope + " AND stage='production'",
                       [first, nxt])
    quote_total, quote_monthly = int(stats['total']), int(stats['monthly'])
    success_monthly = php_round(100 * int(stats['monthly_won']) / quote_monthly, 2) if quote_monthly else 0
    success_total = php_round(100 * int(stats['won']) / quote_total, 2) if quote_total else 0
    dashboard = [
        ('Monthly leads', monthly_leads), ('Total leads', total_leads), ('Monthly quotations', quote_monthly), ('Total quotations', quote_total),
        ('Monthly production orders', int(confirmed['monthly'])), ('Total production orders', int(confirmed['total'])),
        ('Monthly quotation success', fnum(float(success_monthly)) + '%'), ('Total quotation success', fnum(float(success_total)) + '%'),
    ]
    schedule_day = request.args.get('schedule_day', today())
    try:
        schedule_day = wf_date(schedule_day)
    except AppError:
        schedule_day = today()
    schedule_end = add_days(schedule_day, 1)
    schedules = db.rows(
        'SELECT r.*,o.customer,l.name lead_name,q.id quotation_id FROM reminders r LEFT JOIN orders o ON o.id=r.order_id '
        'LEFT JOIN leads l ON l.id=r.lead_id LEFT JOIN wf_quotations q ON q.order_id=o.id WHERE ' +
        ('1=1' if all_access else 'r.salesman_id=%d' % int(u['id'])) + ' AND r.due_at>=%s AND r.due_at<%s ORDER BY r.due_at', [schedule_day, schedule_end])
    return {
        'approved': approved, 'earned': earned, 'target': target, 'pct': pct, 'punch': punch, 'dashboard': dashboard,
        'schedule_day': schedule_day, 'schedules': schedules,
        'new_leads': db.one("SELECT COUNT(*) n FROM leads WHERE " + where + " AND status='new'")['n'],
        'in_review': db.one("SELECT COUNT(*) n FROM orders WHERE " + where + " AND stage='finance'")['n'],
        'order_count': db.one('SELECT COUNT(*) n FROM orders WHERE ' + where)['n'],
    }


def ctx_leads(u, all_access):
    return lead_listing(request.args, u)


def ctx_lead_create(u, all_access):
    lead = None
    if request.args.get('id'):
        lead = owner('leads', to_int(request.args.get('id')), u)
    old = qt_failed_form('lead_update' if lead else 'lead')
    if not old and lead:
        old = lead_form_values(lead)
    return {'lead': lead, 'old': old, 'today': today(), 'people': party_people(u)}


def ctx_orders(u, all_access):
    lead_id = None
    if request.args.get('lead_id'):
        try:
            lead_id = int(owner('leads', to_int(request.args.get('lead_id')), u)['id'])
        except AppError:
            lead_id = None
    args = request.args
    where = ['1=1' if all_access else 'o.salesman_id=%d' % int(u['id'])]
    params = []
    date_from = date_to = ''
    try:
        date_from = wf_date(args['from']) if args.get('from') else ''
    except AppError:
        date_from = ''
    try:
        date_to = wf_date(args['to']) if args.get('to') else ''
    except AppError:
        date_to = ''
    if date_from:
        where.append('o.created_at>=%s')
        params.append(date_from)
    if date_to:
        where.append('o.created_at<%s')
        params.append(add_days(date_to, 1))
    stage = args.get('stage', '')
    if stage not in STAGES:
        stage = ''
    if stage:
        where.append('o.stage=%s')
        params.append(stage)
    search = args.get('search', '').strip()[:100]
    if search:
        where.append('(o.customer LIKE %s OR o.phone LIKE %s OR CAST(o.id AS CHAR) LIKE %s OR u.name LIKE %s)')
        like = '%' + search + '%'
        params.extend([like] * 4)
    where.append("(o.id NOT IN (SELECT order_id FROM wf_surveys) OR o.id IN (SELECT order_id FROM wf_surveys WHERE status IN ('completed','approved')))")
    clause = ' AND '.join(where)
    base = 'FROM orders o JOIN users u ON u.id=o.salesman_id LEFT JOIN wf_quotations q ON q.order_id=o.id WHERE ' + clause
    count_row = db.one('SELECT COUNT(*) n,COALESCE(SUM(o.total),0) amount ' + base, params)
    qty_row = db.one('SELECT COALESCE(SUM(i.quantity),0) qty FROM order_items i WHERE i.order_id IN (SELECT o.id ' + base + ')', params)
    limit = to_int(args.get('limit', 50), 50)
    if limit not in (25, 50, 100, 250, 500):
        limit = 50
    count = int(count_row['n'])
    pages = max(1, -(-count // limit))
    page_no = min(max(1, to_int(args.get('p', 1), 1)), pages)
    offset = (page_no - 1) * limit
    orders = db.rows(
        'SELECT o.*,u.name salesman,q.id quotation_id,q.subtotal q_subtotal,q.discount q_discount,q.grand_total q_grand,'
        '(SELECT COALESCE(SUM(quantity),0) FROM order_items WHERE order_id=o.id) qty,'
        '(SELECT note FROM order_history WHERE order_id=o.id ORDER BY id DESC LIMIT 1) remark,'
        '(SELECT MAX(created_at) FROM order_history WHERE order_id=o.id) updated_at ' + base +
        ' ORDER BY o.id DESC LIMIT %d OFFSET %d' % (limit, offset), params)
    keys = list(STAGES.keys())
    for row in orders:
        index = keys.index(row['stage']) if row['stage'] in keys else 0
        row['progress'] = int(round((index + 1) * 100 / len(keys)))
        row['verified'] = row['stage'] in ('verified', 'production')
    keep = {key: value for key, value in (('from', date_from), ('to', date_to), ('stage', stage), ('search', search), ('limit', limit)) if value not in ('', None)}
    return {
        'request_lead': lead_id, 'orders': orders, 'f_from': date_from, 'f_to': date_to, 'f_stage': stage, 'f_search': search, 'f_limit': limit,
        'o_count': count, 'o_amount': float(count_row['amount']), 'o_qty': float(qty_row['qty']), 'o_page': page_no, 'o_pages': pages,
        'o_offset': offset, 'o_query': urlencode(keep), 'o_range': bool(date_from or date_to),
    }




def ctx_order(u, all_access):
    try:
        o = owner('orders', to_int(request.args.get('id', 0)), u)
    except AppError:
        return {'o': None}
    oid = int(o['id'])
    display = {'finance': 'Finance review', 'production': 'In production'} if o['stage'] in ('finance', 'verified', 'production') else STAGES
    keys = list(display.keys())
    current = 'finance' if o['stage'] == 'verified' else o['stage']
    idx = keys.index(current) if current in keys else -1
    wf = wf_survey(oid)
    ctx = {
        'o': o, 'display_stages': list(display.items()), 'stage_idx': idx, 'next_stage': next_stage(o['stage']), 'wf': wf,
        'items': db.rows('SELECT i.*,p.name FROM order_items i JOIN products p ON p.id=i.product_id WHERE order_id=%s', [oid]),
        'history': db.rows('SELECT h.*,u.name FROM order_history h JOIN users u ON u.id=h.actor_id WHERE order_id=%s ORDER BY h.id DESC', [oid]),
        'wf_ready': False, 'w': None,
    }
    if wf:
        ctx['wf_ready'] = wf_ready(oid)
        ctx['w'] = ctx_workflow(u, o, wf)
    return ctx


def ctx_workflow(u, o, wf):
    oid = int(o['id'])
    wf_edit = wf_can_edit(u) and o['stage'] != 'production' and not has_commission(oid)
    items = wf_items(oid)
    measurements = wf_measurements(oid)
    quote = db.one('SELECT * FROM wf_quotations WHERE order_id=%s', [oid])
    approved = 0
    views = []
    for m in measurements:
        latest = wf_latest_drawing(int(m['id']))
        if latest and latest['status'] == 'approved' and int(latest['survey_revision']) == int(wf['revision']):
            approved += 1
        payload = json_obj(latest['payload']) if latest else {}
        svg = ''
        if latest:
            try:
                svg = wf_drawing_svg(payload)
            except Exception:
                svg = ''
        views.append({
            'm': m, 'drawing': latest, 'payload': payload, 'svg': svg,
            'versions': db.rows('SELECT id,revision,status,created_at FROM wf_drawings WHERE measurement_id=%s ORDER BY revision DESC', [m['id']]),
        })
    failed_survey = qt_failed_form('wf_survey', oid).get('measurements')
    if isinstance(failed_survey, dict):
        survey_rows = list(failed_survey.items())
    else:
        survey_rows = list(enumerate(measurements))
    if not survey_rows:
        survey_rows = [(index, {'order_item_id': item['id'], 'quantity': item['quantity']}) for index, item in enumerate(items)]
    saved_lines = {}
    if quote:
        for line in db.rows('SELECT * FROM wf_quotation_items WHERE quotation_id=%s', [quote['id']]):
            saved_lines[str(line['measurement_id']) if line['measurement_id'] else 'item_%s' % line['order_item_id']] = line
    failed_quote = qt_failed_form('wf_quote', oid)
    qform = dict(quote) if quote else {}
    if failed_quote:
        current = quote['revision'] if quote else 0
        qform.update(failed_quote)
        qform['revision'] = current
    quote_rows = []
    for row in qt_quote_rows(oid):
        key = row['quote_key']
        line = (failed_quote.get('quote_items') or {}).get(key) or saved_lines.get(key)
        ref = 'Survey pending'
        if row['id']:
            latest = wf_latest_drawing(int(row['id']))
            ref = latest['id'] if latest else 'Pending'
        quote_rows.append({'row': row, 'line': line, 'ref': ref, 'key': key})
    survey_done = len({int(m['order_item_id']) for m in measurements if m.get('direction') and m.get('inner_detail') and all(m.get(k) not in (None, '') for k in ('side_top', 'side_bottom', 'side_left', 'side_right'))})
    return {
        'edit': wf_edit, 'items': items, 'measurements': measurements, 'quote': quote, 'approved': approved, 'views': views,
        'survey_rows': survey_rows, 'survey_done': survey_done, 'survey_total': len(items), 'qform': qform, 'quote_rows': quote_rows,
        'quote_history': db.rows('SELECT revision,created_at FROM wf_quotation_revisions WHERE quotation_id=%s ORDER BY revision DESC', [quote['id']]) if quote else [],
        'quote_status': wf_quote_status(quote) if quote else None,
        'default_valid': add_days(today(), 30),
        'today': today(),
        'survey_attachments': wf_attachments(oid, 'survey'),
        'drawing_attachments': wf_attachments(oid, 'drawing'),
        'drawing_options': wf_drawing_options(oid),
    }


def ctx_survey(u, all_access):
    try:
        if u['role'] == 'finance':
            raise AppError('Sales or admin access required.')
        o = owner('orders', to_int(request.args.get('id', 0)), u)
        oid = int(o['id'])
        if not wf_survey(oid):
            raise AppError('Survey is not available for this order.')
        if o['stage'] == 'production':
            raise AppError('Released orders are locked.')
        saved = {}
        for m in wf_measurements(oid):
            saved.setdefault(int(m['order_item_id']), m)
        def side(m, key, fallback):
            if not m:
                return ''
            raw = m.get(key)
            if raw not in (None, ''):
                return str(raw)
            value = float(m[fallback] or 0)
            return ('%g' % value) if value > 0 else ''
        items = []
        for item in wf_items(oid):
            m = saved.get(int(item['id']))
            items.append({
                'id': int(item['id']), 'name': item['name'], 'quantity': int(item['quantity']),
                'top': side(m, 'side_top', 'opening_width'), 'bottom': side(m, 'side_bottom', 'opening_width'),
                'left': side(m, 'side_left', 'opening_height'), 'right': side(m, 'side_right', 'opening_height'),
                'inner': (m.get('inner_detail') or '') if m else '',
                'hinge': m['direction'] if m else '',
                'brand_id': int(m['handle_brand_id']) if m and m.get('handle_brand_id') else '',
                'brand': (m.get('handle_brand') or '') if m else '',
                'frame': (m.get('frame_mode') or 'frame') if m else 'frame', 'unit': (m.get('display_unit') or 'cm') if m else 'cm',
            })
        start = 0
        wanted = to_int(request.args.get('item', 0))
        for index, item in enumerate(items):
            if item['id'] == wanted:
                start = index
        brands = [{'id': int(b['id']), 'name': b['name'], 'company': b['company'] or '', 'details': b['details'] or '', 'image': ('/brand-image?id=%d' % int(b['id'])) if b.get('image') else ''} for b in dh_brands(True)]
        return {'error': None, 'o': o, 'survey_items': items, 'survey_start': start, 'handle_brands': brands, 'survey_status': wf_survey(oid)['status']}
    except Exception as exc:
        return {'error': str(exc), 'o': None, 'survey_items': [], 'survey_start': 0, 'handle_brands': [], 'survey_status': ''}


def ctx_products(u):

    out = {'catalog_error': None, 'catalog': {}}
    if u['role'] != 'finance':
        try:
            out['catalog'] = erp.catalog()
        except Exception as exc:
            out['catalog_error'] = str(exc)
    return out


def ctx_checkout(u, all_access):
    out = {'error': None}
    try:
        if u['role'] == 'finance':
            raise AppError('Sales or admin access required.')
        codes = request.args.getlist('products')
        if not codes or len(codes) > 100:
            raise AppError('Select between 1 and 100 products first.')
        catalog = erp.catalog()
        selected = {}
        for code in codes:
            if code not in catalog:
                raise AppError('A selected product is unavailable. Please select products again.')
            selected[code] = catalog[code]
        lead = None
        if request.args.get('lead_id'):
            lead = owner('leads', to_int(request.args.get('lead_id')), u)
        out.update({
            'selected': list(selected.values()), 'lead': lead, 'today': today(),
            'leads': db.rows('SELECT * FROM leads WHERE ' + ('1=1' if all_access else 'salesman_id=%d' % int(u['id'])) + ' ORDER BY name'),
        })
    except Exception as exc:
        out['error'] = str(exc)
    return out


def ctx_reminders(u):
    lead = None
    if request.args.get('lead_id'):
        try:
            lead = owner('leads', to_int(request.args.get('lead_id')), u)
        except AppError:
            lead = None
    return {'lead': lead}


def ctx_commissions(u, all_access):
    return {'commissions': db.rows('SELECT c.*,o.customer,u.name FROM commissions c JOIN orders o ON o.id=c.order_id JOIN users u ON u.id=c.salesman_id WHERE ' +
                                    ('1=1' if all_access else 'c.salesman_id=%d' % int(u['id'])) + ' ORDER BY c.id DESC LIMIT 300')}


def ctx_team(u=None):
    sync = sync_team(force=False) if u and u['role'] == 'admin' else None
    return {'sync': sync, 'team': db.rows('SELECT id,name,username,email,role,monthly_target,commission_rate,commission_scheme_id,active,avatar FROM users ORDER BY id DESC'),
            'schemes': db.rows('SELECT id,name,percentage FROM commission_schemes ORDER BY name')}



def ctx_quotation_create(u, all_access):
    catalog_error = None
    catalog = {}
    try:
        catalog = erp.catalog()
    except Exception as exc:
        catalog_error = str(exc)
    return {
        'old': qt_failed_form('qt_create'), 'catalog': catalog, 'catalog_error': catalog_error, 'today': today(), 'default_valid': add_days(today(), 30),
        'people': party_people(u),
        'templates': db.rows('SELECT * FROM qt_templates WHERE active=1 ORDER BY title'),
    }


def ctx_quotations(u):
    try:
        listing = qt_listing(request.args, u)
        error = None
    except AppError as exc:
        listing = []
        error = str(exc)
    for row in listing:
        row['details'] = json_obj(row.get('customer_details'))
        row['effective'] = wf_quote_status(row)
        row['display_status'] = 'Converted' if row['stage'] == 'production' else ('Revised' if row['effective'] == 'revised' else (row.get('lead_stage') or 'Quotation'))
    keep = {key: request.args[key] for key in ('from', 'to', 'customer', 'stage', 'status', 'search', 'customer_type') if request.args.get(key)}
    limit = request.args.get('limit', '100')
    if limit not in ('100', '250', '500', '1000', 'All'):
        limit = '100'
    size = 1000 if limit == 'All' else int(limit)
    count = len(listing)
    pages = max(1, -(-count // size))
    page_no = min(max(1, to_int(request.args.get('p', 1), 1)), pages)
    offset = (page_no - 1) * size
    return {
        'listing': listing[offset:offset + size], 'listing_error': error, 'export_query': urlencode(keep), 'q_count': count, 'q_page': page_no,
        'q_pages': pages, 'q_offset': offset, 'q_limit': limit, 'q_keep': keep, 'q_query': urlencode(dict(keep, limit=limit)),
        'q_amount': sum(float(row['grand_total']) for row in listing), 'q_qty': sum(float(row['total_quantity']) for row in listing),
        'q_range': bool(keep.get('from') or keep.get('to')),
    }


def ctx_quote_templates(u):
    return {'all_templates': db.rows('SELECT * FROM qt_templates ORDER BY title') if u['role'] == 'admin' else []}


def ctx_hr(u, page):
    out = {'hr_error': None}
    try:
        month = hr_month(request.args.get('month', php_date('Y-m')))
        employee_args = request.args.get('employee_id')
        if page == 'salary' and u['role'] == 'admin' and employee_args is None:
            first = db.one("SELECT id FROM users WHERE role='salesman' ORDER BY active DESC,name LIMIT 1")
            if first:
                employee_args = str(first['id'])
        employee = hr_employee(u, employee_args)
        uid = int(employee['id'])
        year = int(month[:4])
        out.update({'month': month, 'employee': employee, 'uid': uid, 'year': year, 'month_label': php_date('F Y', month + '-01'), 'today': today()})
        if u['role'] == 'admin':
            if page == 'salary':
                queue = db.rows("SELECT a.user_id,a.amount,a.deduction_month,a.status,u.name FROM salary_advances a JOIN users u ON u.id=a.user_id "
                                "WHERE a.status IN ('pending','approved') ORDER BY a.created_at LIMIT 50")
            else:
                queue = db.rows("SELECT l.user_id,l.start_date,l.end_date,u.name FROM leave_requests l JOIN users u ON u.id=l.user_id "
                                "WHERE l.status='pending' ORDER BY l.created_at LIMIT 50")
            out['queue'] = queue
            out['people'] = db.rows('SELECT id,name,role,active FROM users' + (" WHERE role='salesman'" if page == 'salary' else '') + ' ORDER BY name')
        if page != 'salary':
            calendar = hr_attendance(month, uid)
            first = to_dt(month + '-01')
            prev_month = add_months(first, -1).strftime('%Y-%m')
            next_month = add_months(first, 1).strftime('%Y-%m')
            cells = [None] * calendar['offset'] + calendar['days']
            while len(cells) % 7:
                cells.append(None)
            out.update({
                'calendar': calendar, 'prev_month': prev_month, 'next_month': next_month, 'this_month': php_date('Y-m'),
                'weeks': [cells[i:i + 7] for i in range(0, len(cells), 7)],
                'punch': db.one('SELECT * FROM attendance WHERE user_id=%s AND day=%s', [u['id'], today()]),
                'attendance_list': db.rows('SELECT a.*,u.name FROM attendance a JOIN users u ON u.id=a.user_id WHERE ' +
                                           ('1=1' if privileged(u) else 'a.user_id=%d' % int(u['id'])) + ' ORDER BY a.id DESC LIMIT 100'),
                'leaves': db.rows('SELECT l.*,u.name FROM leave_requests l JOIN users u ON u.id=l.user_id WHERE l.user_id=%s AND l.start_date<=%s AND l.end_date>=%s '
                                  'ORDER BY l.created_at DESC', [uid, php_date('Y-m-t', month + '-01'), month + '-01']),
                'workdays': hr_workdays(),
                'weekdays': (('1', 'Monday'), ('2', 'Tuesday'), ('3', 'Wednesday'), ('4', 'Thursday'), ('5', 'Friday'), ('6', 'Saturday'), ('7', 'Sunday')),
            })
        elif employee['role'] == 'salesman':
            profile = db.one('SELECT * FROM employee_salary WHERE user_id=%s', [uid])
            report = db.one('SELECT * FROM salary_reports WHERE user_id=%s AND salary_month=%s', [uid, month])
            annual = {}
            for row in db.rows('SELECT * FROM salary_reports WHERE user_id=%s AND salary_month BETWEEN %s AND %s ORDER BY salary_month', [uid, '%04d-01' % year, '%04d-12' % year]):
                annual[row['salary_month']] = row
            annual_total = sum(float(row['net_salary']) for row in annual.values())
            annual_paid = sum(float(row['net_salary']) for row in annual.values() if row['paid_at'])
            out.update({
                'profile': profile, 'report': report, 'advances': hr_advance_total(uid, month), 'annual_total': annual_total, 'annual_paid': annual_paid,
                'annual_rows': [('%04d-%02d' % (year, n), annual.get('%04d-%02d' % (year, n))) for n in range(1, 13)],
                'requests': db.rows('SELECT * FROM salary_advances WHERE user_id=%s ORDER BY id DESC', [uid]),
                'current_month': php_date('Y-m'),
            })
    except db.MySQLError as exc:
        current_app.logger.error('HR view failed: %r', exc)
        out['hr_error'] = 'Unable to load the report. Please try again.'
    except AppError as exc:
        out['hr_error'] = str(exc)
    return out


def build_context(u, page):
    all_access = privileged(u)
    reminders = db.rows('SELECT r.*,u.name FROM reminders r JOIN users u ON u.id=r.salesman_id WHERE r.done=0 AND ' +
                        ('1=1' if all_access else 'r.salesman_id=%d' % int(u['id'])) + ' ORDER BY r.due_at LIMIT 100')
    stamp = now().strftime('%Y-%m-%d %H:%M:%S')
    due = len([r for r in reminders if str(r['due_at']) <= stamp])
    ctx = {'u': u, 'page': page, 'all_access': all_access, 'reminders': reminders, 'due': due}
    if page == 'home':
        ctx.update(ctx_home(u, all_access, reminders))
    elif page == 'leads':
        ctx.update(ctx_leads(u, all_access))
    elif page == 'lead_create':
        ctx.update(ctx_lead_create(u, all_access))
    elif page == 'orders':
        ctx.update(ctx_orders(u, all_access))
    elif page == 'order':
        ctx.update(ctx_order(u, all_access))
    elif page == 'survey':
        ctx.update(ctx_survey(u, all_access))
    elif page == 'products':
        ctx.update(ctx_products(u))
    elif page == 'checkout':
        ctx.update(ctx_checkout(u, all_access))
    elif page == 'reminders':
        ctx.update(ctx_reminders(u))
    elif page == 'commissions':
        ctx.update(ctx_commissions(u, all_access))
    elif page == 'commission_schemes':
        ctx.update({'schemes': db.rows('SELECT s.*,(SELECT COUNT(*) FROM users x WHERE x.commission_scheme_id=s.id) members FROM commission_schemes s ORDER BY s.name')})
    elif page == 'team':
        ctx.update(ctx_team(u))
    elif page == 'quotation_create':
        ctx.update(ctx_quotation_create(u, all_access))
    elif page in ('quotations', 'order_forms'):
        ctx.update(ctx_quotations(u))
    elif page == 'quote_templates':
        ctx.update(ctx_quote_templates(u))
    elif page == 'deletion_logs':
        ctx.update(log_listing(request.args))
    elif page == 'door_handles':
        ctx.update({'brands': dh_brands() if u['role'] == 'admin' else []})
    elif page in ('attendance', 'salary', 'calendar'):
        ctx.update(ctx_hr(u, page))
    return ctx


def index():
    u = user()
    if u:
        try:
            schema.ensure_all()
        except Exception:
            current_app.logger.exception('Schema setup failed')
            return Response('Database setup could not finish. Check the database user permissions (CREATE and ALTER) and the server log. '
                            'Existing data has not been removed.', 503)
    if request.method == 'POST':
        return actions.handle_post()
    page = request.args.get('page', 'home')
    if u and u.get('employee_id') and avatar_refresh(u):
        reset_user_cache()
        u = user()
    if page not in ALLOWED_PAGES:
        page = 'home'
    if page in ('team', 'commission_schemes', 'deletion_logs') and (not u or u['role'] != 'admin'):
        page = 'home'
    notices = []
    for key in ('flash', 'error'):
        if key in session:
            notices.append((key, session.pop(key)))
    if not u:
        return render_template('login.html', notices=notices)
    if u['role'] == 'freelancer' and page in FREELANCER_HIDDEN:
        page = 'home'
    ctx = build_context(u, page)
    ctx['notices'] = notices
    ctx['nav'] = tuple(item for item in NAV if not (u['role'] == 'freelancer' and item[0] in FREELANCER_HIDDEN))
    ctx['bottom_nav'] = BOTTOM_NAV
    return render_template('index.html', **ctx)


def reminders_json():
    u = user()
    if not u:
        return Response('[]', 401, mimetype='application/json')
    rows = db.rows('SELECT id,title,due_at FROM reminders WHERE done=0 AND due_at<=%s AND ' + ('1=1' if privileged(u) else 'salesman_id=%d' % int(u['id'])) +
                   ' ORDER BY due_at LIMIT 100', [now().strftime('%Y-%m-%d %H:%M:%S')])
    return Response(json.dumps(rows, default=str), mimetype='application/json')


def selfie():
    u = user()
    if not u:
        abort(401)
    record = db.one('SELECT * FROM attendance WHERE id=%s', [to_int(request.args.get('id', 0))])
    if not record or (not privileged(u) and int(record['user_id']) != int(u['id'])):
        abort(404)
    path = config.SELFIE_DIR / re.split(r'[\\/]', record['selfie'])[-1]
    if not path.is_file():
        abort(404)
    mime = {'jpg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}.get(path.suffix.lstrip('.').lower(), 'application/octet-stream')
    response = send_file(path, mimetype=mime)
    response.headers['Content-Disposition'] = 'inline'
    return response


def avatar():
    u = user()
    if not u:
        abort(401)
    record = db.one('SELECT avatar FROM users WHERE id=%s', [to_int(request.args.get('id', 0))])
    if not record or not record['avatar']:
        abort(404)
    path = config.AVATAR_DIR / re.split(r'[\\/]', record['avatar'])[-1]
    if not path.is_file():
        abort(404)
    mime = {'jpg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}.get(path.suffix.lstrip('.').lower(), 'application/octet-stream')
    response = send_file(path, mimetype=mime)
    response.headers['Content-Disposition'] = 'inline'
    response.headers['Cache-Control'] = 'private, max-age=86400'
    return response


def brand_image():
    u = user()
    if not u:
        abort(401)
    record = db.one('SELECT image FROM door_handle_brands WHERE id=%s', [to_int(request.args.get('id', 0))])
    if not record or not record['image']:
        abort(404)
    path = config.BRAND_DIR / re.split(r'[\\/]', record['image'])[-1]
    if not path.is_file():
        abort(404)
    mime = {'jpg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}.get(path.suffix.lstrip('.').lower(), 'application/octet-stream')
    response = send_file(path, mimetype=mime)
    response.headers['Content-Disposition'] = 'inline'
    return response


def wf_item_codes(item_ids):
    ids = sorted({to_int(i) for i in item_ids if to_int(i)})
    if not ids:
        return {}
    marks = ','.join(['%s'] * len(ids))
    try:
        found = db.rows('SELECT i.id,e.item_code,i.product_id FROM order_items i LEFT JOIN erp_products e ON e.product_id=i.product_id WHERE i.id IN (' + marks + ')', ids)
    except Exception:
        found = db.rows('SELECT id,NULL item_code,product_id FROM order_items WHERE id IN (' + marks + ')', ids)
    return {int(row['id']): row['item_code'] or 'ITM-%04d' % int(row['product_id']) for row in found}


def workflow_file():
    u = user()
    if not u:
        return Response('Sign in required.', 401)
    try:
        if 'attachment' in request.args:
            record = db.one('SELECT * FROM wf_attachments WHERE id=%s', [to_int(request.args.get('attachment'))])
            if not record:
                raise AppError('Attachment unavailable.')
            owner('orders', int(record['order_id']), u)
            path = config.WORKFLOW_DIR / re.split(r'[\\/]', record['filename'])[-1]
            if not path.is_file():
                raise AppError('Attachment unavailable.')
            preview = 'preview' in request.args and record['mime'] in ('image/jpeg', 'image/png', 'application/pdf')
            response = send_file(path, mimetype=record['mime'] if preview else 'application/octet-stream')
            from urllib.parse import quote as urlquote
            response.headers['Content-Security-Policy'] = "sandbox; default-src 'none'"
            response.headers['Content-Disposition'] = '%s; filename="attachment-%d.%s"; filename*=UTF-8\'\'%s' % (
                'inline' if preview else 'attachment', int(record['id']), path.suffix.lstrip('.'), urlquote(record['original_name'], safe=''))
            return response
        if 'drawing' in request.args:
            drawing = db.one('SELECT * FROM wf_drawings WHERE id=%s', [to_int(request.args.get('drawing'))])
            if not drawing:
                raise AppError('Drawing unavailable.')
            order = owner('orders', int(drawing['order_id']), u)
            payload = json.loads(drawing['payload'])
            svg = wf_drawing_svg(payload)
            if 'download' in request.args:
                return Response(svg, mimetype='image/svg+xml', headers={'Content-Disposition': 'attachment; filename="order-%s-drawing-%s-r%s.svg"' % (
                    order['id'], drawing['id'], drawing['revision'])})
            return render_template('document.html', kind='drawing', drawing=drawing, payload=payload, svg=svg, order=order,
                                   title='Drawing #%s \u00b7 Revision %s' % (drawing['id'], drawing['revision']))
        if 'quotation' in request.args:
            quote = db.one('SELECT * FROM wf_quotations WHERE id=%s', [to_int(request.args.get('quotation'))])
            if not quote:
                raise AppError('Quotation unavailable.')
            order = owner('orders', int(quote['order_id']), u)
            customer = order
            historical = False
            if 'revision' in request.args:
                snapshot = db.one('SELECT * FROM wf_quotation_revisions WHERE quotation_id=%s AND revision=%s', [quote['id'], to_int(request.args.get('revision'))])
                if not snapshot:
                    raise AppError('Revision unavailable.')
                saved = json.loads(snapshot['payload'])
                quote = saved['quote']
                lines = saved['items']
                customer = saved['customer']
                historical = True
            else:
                lines = db.rows('SELECT * FROM wf_quotation_items WHERE quotation_id=%s ORDER BY id', [quote['id']])
            for line in lines:
                line['m'] = json_obj(line.get('snapshot'))
                if not historical and line.get('measurement_id'):
                    live = db.one('SELECT frame_mode,display_unit FROM wf_measurements WHERE id=%s', [line['measurement_id']])
                    if live:
                        line['m'].update(live)
            company = json_obj(quote['company_snapshot'])
            order_form = 'order_form' in request.args
            seller = db.one('SELECT name FROM users WHERE id=%s', [order['salesman_id']])
            salesman_name = seller['name'] if seller else ''
            codes = wf_item_codes(line.get('order_item_id') for line in lines) if order_form else {}
            for line in lines:
                line['code'] = codes.get(to_int(line.get('order_item_id')), '')
            label = 'Order Form' if order_form else 'Quotation'
            return render_template('document.html', kind='quotation', quote=quote, lines=lines, customer=customer, customer_meta=json_obj(quote.get('customer_details')),
                                   company=company, historical=historical, order=order, quote_number=wf_quote_number(quote), order_form=order_form, salesman_name=salesman_name,
                                   title='%s %s \u00b7 r%s' % (label, wf_quote_number(quote), quote['revision']))
        raise AppError('Document unavailable.')
    except Redirect:
        raise
    except Exception:
        return Response('Document unavailable.', 404)


def quotations_export():
    u = user()
    if not u:
        return Response('Sign in required.', 401)
    try:
        listing = qt_listing(request.args, u)
    except AppError:
        return Response('Invalid quotation filters.', 422)
    buffer = io.StringIO()
    buffer.write('\ufeff')
    writer = csv.writer(buffer)
    writer.writerow(['Voucher', 'Customer', 'Phone', 'Status', 'Contact Date', 'Quantity', 'Subtotal', 'Discount', 'Grand Total', 'Date', 'Updated'])
    for q in listing:
        meta = json_obj(q.get('customer_details'))
        row = [wf_quote_number(q), q['customer'], q['phone'], wf_quote_status(q), meta.get('contact_date', ''), q['total_quantity'], q['subtotal'],
               q['discount'], q['grand_total'], q['quote_date'], q['updated_at']]
        row = [("'" + str(cell)) if re.match(r'^[=+@\-\t\r\n]', str(cell)) else cell for cell in row]
        writer.writerow(row)
    return Response(buffer.getvalue(), mimetype='text/csv; charset=UTF-8',
                    headers={'Content-Disposition': 'attachment; filename="quotations-%s.csv"' % today()})


def api_import():
    def reply(status, body):
        return Response(json.dumps(body), status, mimetype='application/json')

    if request.method != 'POST':
        return reply(405, {'error': 'POST required'})
    token = config.IMPORT_TOKEN or ''
    auth = request.headers.get('Authorization', '')
    if len(token) < 32 or not hash_equals('Bearer ' + token, auth):
        return reply(401, {'error': 'Unauthorized'})
    raw = request.get_data(cache=False)[:65537]
    if len(raw) > 65536:
        return reply(413, {'error': 'Payload too large'})
    data = {}
    try:
        data = json.loads(raw.decode('utf-8'))
        if not isinstance(data, dict):
            raise AppError('JSON object required')
        for key in ('external_ref', 'customer', 'phone', 'address'):
            value = data.get(key)
            limit = 3000 if key == 'address' else (30 if key == 'phone' else 150)
            if not isinstance(value, str) or value.strip() == '' or len(value.encode('utf-8')) > limit:
                raise AppError('Invalid ' + key)
        from .core import filter_int
        sid = filter_int(data.get('salesman_id'))
        sales = db.one("SELECT * FROM users WHERE id=%s AND role IN ('salesman','freelancer','fabricator') AND active=1", [sid or 0])
        if not sales:
            raise AppError('Active salesman or freelancer required')
        items = data.get('items')
        if not isinstance(items, list) or not items or len(items) > 100:
            raise AppError('1\u2013100 items required')
        checked = []
        total = 0
        for item in items:
            item = item if isinstance(item, dict) else {}
            qty = filter_int(item.get('quantity'))
            pid = filter_int(item.get('product_id'))
            product = db.one('SELECT * FROM products WHERE id=%s AND active=1', [pid or 0])
            if not product or not qty or qty < 1 or qty > 10000:
                raise AppError('Invalid product or quantity')
            checked.append((product, qty))
            total += float(product['price']) * qty
        if total > 999999999:
            raise AppError('Order total exceeds limit')
        db.begin()
        db.q("INSERT INTO orders(salesman_id,customer,phone,address,source,external_ref,total,commission_rate,stage) VALUES (%s,%s,%s,%s,'ecommerce',%s,%s,%s,'finance')",
             [sid, data['customer'].strip(), data['phone'].strip(), data['address'].strip(), data['external_ref'], total, sales['commission_rate']])
        oid = db.insert_id()
        for product, qty in checked:
            db.q('INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES (%s,%s,%s,%s)', [oid, product['id'], qty, product['price']])
        db.q("INSERT INTO order_history(order_id,actor_id,stage,note) VALUES (%s,%s,'finance','Imported from ecommerce for finance review')", [oid, sid])
        db.commit()
        return reply(201, {'order_id': oid})
    except Exception as exc:
        db.rollback()
        if isinstance(exc, db.MySQLError):
            if exc.args and exc.args[0] == 1062:
                existing = db.one('SELECT id FROM orders WHERE external_ref=%s', [data.get('external_ref', '') if isinstance(data, dict) else ''])
                return reply(200, {'order_id': existing['id'] if existing else None, 'duplicate': True})
            current_app.logger.error('Import failed: %r', exc)
            return reply(500, {'error': 'Import failed'})
        if isinstance(exc, (AppError, ValueError)):
            return reply(422, {'error': str(exc)})
        current_app.logger.exception('Import failed')
        return reply(500, {'error': 'Import failed'})


def install():
    enabled = config.INSTALL_ENABLED
    key = config.INSTALL_KEY or ''
    if not enabled or len(key) < 32 or key.startswith('REPLACE_'):
        return Response('Installer disabled. Set ZIVOC_INSTALL_ENABLED=1 and a private ZIVOC_INSTALL_KEY of at least 32 characters in .env.', 403)
    lock = config.STORAGE_DIR / 'installed.lock'
    complete = lock.is_file()
    error = ''
    reset_done = False
    if request.method == 'POST':
        try:
            if not hash_equals(csrf_token(), request.form.get('csrf', '')):
                raise AppError('Session expired. Reload and try again.')
            if not hash_equals(key, request.form.get('install_key', '')):
                raise AppError('Incorrect installer key. Copy the key from your .env file.')
            if 'reset_admin' in request.form:
                if not db.one("SHOW COLUMNS FROM users LIKE 'username'"):
                    db.q('ALTER TABLE users ADD COLUMN username VARCHAR(80) NULL UNIQUE AFTER name')
                hashed = hash_password('Apple@123')
                admin = db.one("SELECT id FROM users WHERE username='admin' LIMIT 1")
                if admin:
                    db.q("UPDATE users SET password=%s, role='admin', active=1 WHERE id=%s", [hashed, admin['id']])
                else:
                    email = 'admin@zivoc.invalid'
                    if db.one('SELECT id FROM users WHERE email=%s', [email]):
                        email = 'admin-' + secrets.token_hex(8) + '@zivoc.invalid'
                    db.q("INSERT INTO users(name,username,email,password,role,active) VALUES ('Administrator','admin',%s,%s,'admin',1)", [email, hashed])
                db.q('DELETE FROM login_attempts WHERE ip=%s', [actions.client_ip()])
                reset_done = True
            elif not complete:
                config.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
                config.SELFIE_DIR.mkdir(parents=True, exist_ok=True)
                config.WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
                config.SESSION_DIR.mkdir(parents=True, exist_ok=True)
                schema.apply_schema()
                schema.ensure_role_schema()
                if not db.one("SHOW COLUMNS FROM users LIKE 'username'"):
                    db.q('ALTER TABLE users ADD COLUMN username VARCHAR(80) NULL UNIQUE AFTER name')
                existing = db.one('SELECT id,role FROM users WHERE username=%s', ['admin'])
                if existing and existing['role'] != 'admin':
                    raise AppError('Username admin is already used by a non-admin account. Resolve this conflict before continuing.')
                if not existing:
                    email = 'admin@zivoc.invalid'
                    if db.one('SELECT id FROM users WHERE email=%s', [email]):
                        email = 'admin-' + secrets.token_hex(8) + '@zivoc.invalid'
                    db.q("INSERT INTO users(name,username,email,password,role) VALUES ('Administrator','admin',%s,%s,'admin')", [email, hash_password('Apple@123')])
                lock.write_text(now().isoformat())
                complete = True
        except AppError as exc:
            error = str(exc)
        except db.MySQLError as exc:
            current_app.logger.error('Install failed: %r', exc)
            error = 'Database setup failed. Verify the selected database, permissions and server error log. Existing records have not been deleted; you can retry after fixing the cause.'
    return render_template('install.html', complete=complete, error=error, reset_done=reset_done)


def pos_sync():
    token = config.IMPORT_TOKEN or ''
    bearer = request.headers.get('Authorization', '')
    u = user()
    allowed = (u and u['role'] == 'admin') or (len(token) >= 32 and hash_equals('Bearer ' + token, bearer))
    if not allowed:
        return Response(json.dumps({'success': False, 'message': 'Unauthorized'}), 401, mimetype='application/json')
    from .pos import sync_employees
    body, status = sync_employees()
    return Response(json.dumps(body, indent=4, default=str), status, mimetype='application/json')


def register(app):
    from . import ui
    ui.register(app)
    app.jinja_env.filters.update(cm=cm_text, cmu=cm_unit, dimu=dim_unit)
    app.jinja_env.globals.update(
        wf_label=wf_label, wf_quote_number=wf_quote_number, wf_quote_status=wf_quote_status, wf_can_edit=wf_can_edit, wf_latest_drawing=wf_latest_drawing,
        positive_value=positive_value, privileged=privileged, WF_MEASURES=WF_MEASURES, STAGES=STAGES, csrf_token=csrf_token, to_int=to_int,
        asset_version=asset_version, fnum=fnum, now_year=lambda: php_date('Y'),
    )
    app.add_url_rule('/', 'index', index, methods=['GET', 'POST'])
    app.add_url_rule('/index.php', 'index_php', index, methods=['GET', 'POST'])
    app.add_url_rule('/api', 'api_import', api_import, methods=['GET', 'POST'])
    app.add_url_rule('/api.php', 'api_import_php', api_import, methods=['GET', 'POST'])
    app.add_url_rule('/reminders', 'reminders_json', reminders_json)
    app.add_url_rule('/selfie', 'selfie', selfie)
    app.add_url_rule('/brand-image', 'brand_image', brand_image)
    app.add_url_rule('/avatar', 'avatar', avatar)
    app.add_url_rule('/workflow-file', 'workflow_file', workflow_file)
    app.add_url_rule('/quotations-export', 'quotations_export', quotations_export)
    app.add_url_rule('/install', 'install', install, methods=['GET', 'POST'])
    app.add_url_rule('/pos-sync', 'pos_sync', pos_sync, methods=['GET', 'POST'])


def asset_version(name):
    try:
        return int((config.BASE_DIR / 'zivoc' / 'assets' / name).stat().st_mtime)
    except OSError:
        return 0
