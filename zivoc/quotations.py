import json

from flask import session

from . import catalog as erp
from . import db
from .core import AppError
from .helpers import owner, privileged, require_admin, required, salesman, val
from .core import post
from .leads import LEAD_STAGES, insert_lead
from .workflow import WF_MEASURES, wf_action, wf_can_edit, wf_date, wf_items, wf_log, wf_measurements, wf_number, wf_quantity, wf_text

CUSTOMER_TYPES = ('new', 'existing', 'franchise')
STATUS_EXPR = "CASE WHEN q.status IN ('draft','sent','revised') AND q.valid_until<CURRENT_DATE THEN 'expired' ELSE q.status END"


def _coalesce(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _json_dict(text):
    try:
        data = json.loads(text) if text else None
    except ValueError:
        data = None
    return data if isinstance(data, dict) else {}


def qt_failed_form(action, oid=0):
    saved = session.get('save_form') or {}
    if saved.get('action') == action and (not oid or int(saved.get('order_id') or 0) == oid):
        return saved
    return {}


def qt_template_id(value):
    if value is None or value == '':
        return None
    from .core import filter_int
    template_id = filter_int(value)
    if not template_id or not db.one('SELECT id FROM qt_templates WHERE id=%s AND active=1', [template_id]):
        raise AppError('Choose an available terms template.')
    return template_id


def qt_customer_details(data, order):
    existing = db.one('SELECT customer_details FROM wf_quotations WHERE order_id=%s', [order['id']])
    previous = _json_dict(existing['customer_details'] if existing else None)
    default_type = 'existing' if order['lead_id'] else 'new'
    kind = wf_text(_coalesce(data.get('customer_type'), previous.get('customer_type'), default_type), 15)
    if kind not in CUSTOMER_TYPES:
        raise AppError('Invalid customer type.')
    out = {'customer_type': kind}
    for key in ('address1', 'address2', 'postal_code', 'post_office', 'state', 'district', 'end_customer', 'remark', 'contact_date'):
        fallback = order['address'] if key == 'address1' else ''
        out[key] = wf_text(_coalesce(data.get(key), previous.get(key), fallback), 2000 if key in ('end_customer', 'remark') else 500)
    if out['contact_date'] != '':
        wf_date(out['contact_date'])
    return out


def qt_quote_rows(oid):
    rows = wf_measurements(oid)
    covered = {}
    for row in rows:
        row['quote_key'] = str(row['id'])
        covered[int(row['order_item_id'])] = covered.get(int(row['order_item_id']), 0) + int(row['quantity'])
    for item in wf_items(oid):
        done = covered.get(int(item['id']), 0)
        if done < int(item['quantity']):
            row = {
                'id': 0,
                'order_item_id': item['id'],
                'quote_key': 'item_%s' % item['id'],
                'quantity': int(item['quantity']) - done,
                'unit_price': item['unit_price'],
                'name': item['name'],
                'location': 'Survey pending',
                'direction': '',
                'opening_type': '',
                'site_notes': '',
                'requirements': '',
            }
            for key in WF_MEASURES:
                row[key] = 0
            rows.append(row)
    return rows


def qt_action(action, u):
    if action == 'qt_template':
        require_admin(u)
        from .core import filter_int
        template_id = filter_int(val('template_id')) or 0
        name = required('title', 150)
        terms = required('terms', 5000)
        if template_id:
            if not db.one('SELECT id FROM qt_templates WHERE id=%s', [template_id]):
                raise AppError('Template unavailable.')
            db.q('UPDATE qt_templates SET title=%s,terms=%s,active=%s WHERE id=%s', [name, terms, 0 if val('active') == '0' else 1, template_id])
        else:
            db.q('INSERT INTO qt_templates(title,terms,created_by) VALUES (%s,%s,%s)', [name, terms, u['id']])
        return True
    if action != 'qt_create':
        return False
    session.pop('quote_created_order', None)
    if not wf_can_edit(u):
        raise AppError('Sales or admin access required.')
    kind = required('customer_type', 15)
    if kind not in CUSTOMER_TYPES:
        raise AppError('Choose a customer type.')
    from .helpers import to_int
    lead_id = to_int(val('lead_id'))
    lead = owner('leads', lead_id, u) if lead_id else None
    if kind == 'existing' and not lead:
        raise AppError('Select an existing lead/customer.')
    sid = int(lead['salesman_id']) if lead else salesman(u)
    name = lead['name'] if lead else required('customer', 150)
    phone = lead['phone'] if lead else required('phone', 30)
    address = (val('address1', 500) + '\n' + val('address2', 500)).strip()
    if address == '':
        address = lead['address'] if lead else ''
    if address == '':
        raise AppError('Customer address is required.')
    data = post()
    raw = data.get('qt_items', {})
    if not isinstance(raw, dict) or not raw or len(raw) > 100:
        raise AppError('Add 1\u2013100 products to the quotation.')
    catalog = erp.catalog()
    lines = []
    total = 0
    for line in raw.values():
        if not isinstance(line, dict):
            raise AppError('Invalid product row.')
        code = wf_text(line.get('code', ''), 190)
        if code not in catalog:
            raise AppError('A product is no longer available.')
        quantity = wf_quantity(line.get('quantity'))
        price = wf_number(line.get('unit_price', 0))
        product_id = erp.local_product(catalog[code])
        lines.append((product_id, quantity, price))
        total += quantity * price
    if total > 999999999:
        raise AppError('Quotation subtotal exceeds limit.')
    db.begin()
    if not lead:
        lead_id = insert_lead(sid, {
            'name': name, 'phone': phone, 'address': val('address1', 500), 'address2': val('address2', 500), 'postal_code': val('postal_code', 20),
            'post_office': val('post_office', 190), 'state': val('state', 100), 'district': val('district', 100), 'notes': 'Created from quotation',
            'lead_date': wf_date(val('quote_date', 10)), 'customer_type': kind, 'contact_date': val('contact_date', 10), 'stage': 'Quotation',
        })
    else:
        db.q("UPDATE leads SET stage='Quotation' WHERE id=%s AND stage IN ('Lead','Oppurtunity','Oppurtunity 50%%','Oppurtunity 75%%','Oppurtunity 90%%')", [lead_id])
    rate = db.one('SELECT commission_rate FROM users WHERE id=%s', [sid])['commission_rate']
    db.q("INSERT INTO orders(salesman_id,lead_id,customer,phone,address,source,total,commission_rate,stage) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'order')",
         [sid, lead_id, name, phone, address, u['role'], total, rate])
    oid = int(db.insert_id())
    quote_items = {}
    for product_id, quantity, price in lines:
        db.q('INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES (%s,%s,%s,%s)', [oid, product_id, quantity, price])
        quote_items['item_%s' % db.insert_id()] = {'quantity': quantity, 'unit_price': price}
    db.q('INSERT INTO wf_surveys(order_id,updated_by) VALUES (%s,%s)', [oid, u['id']])
    data['order_id'] = oid
    data['revision'] = 0
    data['quote_items'] = quote_items
    wf_action('wf_quote', u, False)
    contact = val('contact_date', 10)
    if contact != '':
        db.q('INSERT INTO reminders(salesman_id,order_id,lead_id,title,due_at) VALUES (%s,%s,%s,%s,%s)',
             [sid, oid, lead_id, 'Quotation follow-up: ' + name, wf_date(contact) + ' 09:00:00'])
    wf_log(oid, u, 'quotation', 'Quotation created from customer and products. Survey/drawing preparation remains available.')
    db.commit()
    session['quote_created_order'] = oid
    return True


def qt_filter(data, u):
    where = ['1=1' if privileged(u) else 'o.salesman_id=%s']
    params = [] if privileged(u) else [u['id']]
    for key, operator in (('from', '>='), ('to', '<=')):
        if data.get(key) not in (None, '', '0'):
            date = wf_date(wf_text(data.get(key), 10))
            where.append('q.quote_date ' + operator + ' %s')
            params.append(date)
    if data.get('from') not in (None, '', '0') and data.get('to') not in (None, '', '0') and data.get('from') > data.get('to'):
        raise AppError('From date must be before To date.')
    status = wf_text(data.get('status', ''), 20)
    if status != '':
        if status not in ('draft', 'sent', 'approved', 'rejected', 'revised', 'expired', 'converted'):
            raise AppError('Invalid status filter.')
        if status == 'converted':
            where.append("o.stage='production'")
        else:
            where.append(STATUS_EXPR + '=%s')
            params.append(status)
    kind = wf_text(data.get('customer_type', ''), 15)
    if kind != '':
        if kind not in CUSTOMER_TYPES:
            raise AppError('Invalid customer filter.')
        where.append("COALESCE(JSON_UNQUOTE(JSON_EXTRACT(q.customer_details,'$.customer_type')),'existing')=%s")
        params.append(kind)
    customer = wf_text(data.get('customer', ''), 15)
    if customer == 'Individual':
        where.append("COALESCE(JSON_UNQUOTE(JSON_EXTRACT(q.customer_details,'$.customer_type')),'existing') IN ('new','existing')")
    elif customer == 'Franchise':
        where.append("COALESCE(JSON_UNQUOTE(JSON_EXTRACT(q.customer_details,'$.customer_type')),'existing')='franchise'")
    stage = wf_text(data.get('stage', ''), 30)
    if stage == 'Converted':
        where.append("o.stage='production'")
    elif stage in LEAD_STAGES:
        where.append("o.stage<>'production' AND COALESCE(l.stage,'Quotation')=%s")
        params.append(stage)
    search = wf_text(data.get('search', ''), 150)
    if search != '':
        where.append('(o.customer LIKE %s OR o.phone LIKE %s OR CAST(q.id AS CHAR) LIKE %s)')
        like = '%' + search + '%'
        params.extend([like, like, like])
    return ' AND '.join(where), params


def qt_listing(data, u):
    where, params = qt_filter(data, u)
    return db.rows(
        'SELECT q.*,o.customer,o.phone,o.stage,o.id order_number,o.created_at entry_at,l.stage lead_stage,l.status_remark lead_status_remark,'
        '(SELECT COALESCE(SUM(quantity),0) FROM wf_quotation_items qi WHERE qi.quotation_id=q.id) total_quantity '
        'FROM wf_quotations q JOIN orders o ON o.id=q.order_id LEFT JOIN leads l ON l.id=o.lead_id WHERE ' + where + ' ORDER BY q.quote_date DESC,q.id DESC LIMIT 1000',
        params,
    )
