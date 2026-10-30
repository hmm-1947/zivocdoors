from urllib.parse import urlencode

from . import db
from .core import AppError
from .erpleads import push_lead
from .helpers import owner, privileged, required, salesman, to_int, val
from .workflow import wf_date

LEAD_STAGES = ('Lead', 'Oppurtunity', 'Oppurtunity 50%', 'Oppurtunity 75%', 'Oppurtunity 90%', 'Quotation', 'Do not Contact', 'Lost Quotation')
LEAD_TYPES = ('new', 'existing', 'franchise')
LEAD_LIMITS = ('100', '250', '500', '1000', 'All')


def financial_year(day):
    year = int(day[:4])
    month = int(day[5:7])
    start = year if month >= 4 else year - 1
    return '%02d-%02d' % (start % 100, (start + 1) % 100)


def lead_number(row):
    if row.get('lead_no'):
        return row['lead_no']
    day = str(row.get('lead_date') or row.get('created_at') or '2000-01-01')[:10]
    return '%s-LEAD-%04d' % (financial_year(day), int(row['id']))


_PHONE_SQL = "RIGHT(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(phone,' ',''),'-',''),'+',''),'(',''),')',''),10)"


def phone_owner(phone, exclude=None):
    digits = ''.join(ch for ch in str(phone) if ch.isdigit())[-10:]
    if len(digits) < 6:
        return None
    sql = 'SELECT id,name FROM leads WHERE ' + _PHONE_SQL + '=%s'
    args = [digits]
    if exclude:
        sql += ' AND id<>%s'
        args.append(int(exclude))
    return db.one(sql + ' LIMIT 1', args)


def check_phone(phone, exclude=None):
    found = phone_owner(phone, exclude)
    if found:
        raise AppError('Please use a different mobile number. This mobile number is already registered with another lead (%s).' % found['name'])


def insert_lead(sid, data):
    day = data.get('lead_date') or str(db.one('SELECT CURRENT_DATE d')['d'])
    db.q('INSERT INTO leads(salesman_id,name,phone,address,address2,postal_code,post_office,state,district,notes,lead_date,customer_type,contact_date,stage,gst_number) '
         'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
         [sid, data['name'], data['phone'], data.get('address', ''), data.get('address2', ''), data.get('postal_code', ''), data.get('post_office', ''),
          data.get('state', ''), data.get('district', ''), data.get('notes', ''), day, data.get('customer_type', 'new'), data.get('contact_date') or None,
          data.get('stage', 'Lead'), data.get('gst_number', '')])
    lead_id = int(db.insert_id())
    db.q('UPDATE leads SET lead_no=%s WHERE id=%s', ['%s-LEAD-%04d' % (financial_year(day), lead_id), lead_id])
    return lead_id


def _form():
    kind = val('customer_type', 15) or 'new'
    if kind not in LEAD_TYPES:
        raise AppError('Choose a customer type.')
    contact = wf_date(val('contact_date', 10) or str(db.one('SELECT CURRENT_DATE d')['d']))
    return {
        'customer_type': kind,
        'lead_date': wf_date(required('lead_date', 10)),
        'contact_date': contact,
        'name': required('name', 150),
        'phone': required('phone', 30),
        'address': val('address1', 500),
        'address2': val('address2', 500),
        'postal_code': val('postal_code', 20),
        'post_office': val('post_office', 190),
        'state': val('state', 100),
        'district': val('district', 100),
        'notes': val('remark', 3000),
        'gst_number': val('gst_number', 20),
    }


def lead_create(u):
    sid = salesman(u)
    data = _form()
    check_phone(data['phone'])
    db.begin()
    lead_id = insert_lead(sid, data)
    db.q('INSERT INTO reminders(salesman_id,lead_id,title,due_at) VALUES (%s,%s,%s,%s)',
         [sid, lead_id, 'Lead follow-up: ' + data['name'], data['contact_date'] + ' 09:00:00'])
    db.commit()
    push_lead(lead_id)


def lead_update(u):
    record = owner('leads', to_int(val('id')), u)
    data = _form()
    check_phone(data['phone'], record['id'])
    stage = val('stage', 30) or record['stage']
    if stage not in LEAD_STAGES:
        raise AppError('Invalid lead status.')
    db.q('UPDATE leads SET name=%s,phone=%s,address=%s,address2=%s,postal_code=%s,post_office=%s,state=%s,district=%s,notes=%s,lead_date=%s,'
         'customer_type=%s,contact_date=%s,stage=%s,status_remark=%s,gst_number=%s WHERE id=%s',
         [data['name'], data['phone'], data['address'], data['address2'], data['postal_code'], data['post_office'], data['state'], data['district'],
          data['notes'], data['lead_date'], data['customer_type'], data['contact_date'], stage, val('status_remark', 3000), data['gst_number'], record['id']])


def lead_form_values(row):
    out = {
        'lead_date': row['lead_date'], 'customer_type': row['customer_type'], 'name': row['name'], 'phone': row['phone'], 'address1': row['address'],
        'address2': row['address2'], 'postal_code': row['postal_code'], 'post_office': row['post_office'], 'state': row['state'], 'district': row['district'],
        'remark': row['notes'], 'contact_date': row['contact_date'], 'stage': row['stage'], 'status_remark': row['status_remark'], 'gst_number': row.get('gst_number'),
    }
    return {key: ('' if value is None else str(value)) for key, value in out.items()}


def party_people(u):
    where = '1=1' if privileged(u) else 'salesman_id=%d' % int(u['id'])
    rows = db.rows('SELECT id,name,phone,address,address2,postal_code,post_office,state,district,customer_type,salesman_id FROM leads WHERE ' + where +
                   ' ORDER BY name LIMIT 2000')
    return [{key: (int(value) if key in ('id', 'salesman_id') else ('' if value is None else str(value))) for key, value in row.items()} for row in rows]


def lead_listing(args, u):
    where = ['1=1' if privileged(u) else 'l.salesman_id=%d' % int(u['id'])]
    params = []
    date_from = date_to = ''
    for key in ('from', 'to'):
        text = args.get(key, '')
        try:
            text = wf_date(text) if text else ''
        except AppError:
            text = ''
        if key == 'from':
            date_from = text
        else:
            date_to = text
    if date_from:
        where.append('COALESCE(l.lead_date,DATE(l.created_at))>=%s')
        params.append(date_from)
    if date_to:
        where.append('COALESCE(l.lead_date,DATE(l.created_at))<=%s')
        params.append(date_to)
    customer = args.get('customer', '')
    if customer == 'Individual':
        where.append("l.customer_type IN ('new','existing')")
    elif customer == 'Franchise':
        where.append("l.customer_type='franchise'")
    else:
        customer = ''
    raw = args.getlist('status') if hasattr(args, 'getlist') else [args.get('status', '')]
    stage = [item for item in LEAD_STAGES if item in raw]
    if stage:
        where.append('l.stage IN (%s)' % ','.join(['%s'] * len(stage)))
        params.extend(stage)
    search = args.get('search', '').strip()[:100]
    if search:
        where.append('(l.name LIKE %s OR l.phone LIKE %s OR l.lead_no LIKE %s OR l.status_remark LIKE %s OR l.notes LIKE %s)')
        params.extend(['%' + search + '%'] * 5)
    clause = ' AND '.join(where)
    limit = args.get('limit', '100')
    if limit not in LEAD_LIMITS:
        limit = '100'
    count = int(db.one('SELECT COUNT(*) n FROM leads l WHERE ' + clause, params)['n'])
    size = 5000 if limit == 'All' else int(limit)
    pages = max(1, -(-count // size))
    page_no = min(max(1, to_int(args.get('p', 1), 1)), pages)
    offset = (page_no - 1) * size
    rows = db.rows('SELECT l.*,u.name salesman FROM leads l JOIN users u ON u.id=l.salesman_id WHERE ' + clause +
                   ' ORDER BY l.id DESC LIMIT %d OFFSET %d' % (size, offset), params)
    for row in rows:
        row['number'] = lead_number(row)
    keep = {key: value for key, value in (('from', date_from), ('to', date_to), ('customer', customer), ('status', stage), ('search', search)) if value}
    return {
        'leads': rows, 'f_from': date_from, 'f_to': date_to, 'f_customer': customer, 'f_status': stage, 'f_search': search, 'f_limit': limit,
        'l_count': count, 'l_page': page_no, 'l_pages': pages, 'l_offset': offset, 'l_keep': keep, 'l_query': urlencode(dict(keep, limit=limit), doseq=True),
        'l_range': bool(date_from or date_to), 'LEAD_STAGES': LEAD_STAGES, 'LEAD_LIMITS': LEAD_LIMITS,
    }
