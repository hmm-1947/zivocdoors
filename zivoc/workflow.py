import json
import re
import secrets

from flask import session

from . import config, db
from .core import AppError, add_days, files, filter_int, is_numeric, now, php_date, php_round, post, today, ucwords, utf8_len
from .helpers import privileged, required, val
from .uploads import image_info, read_upload

WF_MEASURES = {
    'opening_width': 'Opening width',
    'opening_height': 'Opening height',
    'wall_thickness': 'Wall thickness',
    'frame_width': 'Frame width',
    'frame_height': 'Frame height',
    'shutter_width': 'Shutter width',
    'shutter_height': 'Shutter height',
}

DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def wf_can_edit(u):
    return u['role'] in ('admin', 'salesman', 'freelancer')


def wf_text(value, maximum=2000):
    if isinstance(value, (dict, list, tuple)):
        raise AppError('Invalid text input.')
    text = '' if value is None else str(value).strip()
    if utf8_len(text) > maximum:
        raise AppError('Text exceeds %d characters.' % maximum)
    return text


def wf_number(value, minimum=0, maximum=999999999):
    if isinstance(value, (dict, list, tuple)) or value is None or not is_numeric(value):
        raise AppError('Enter a valid numeric amount or measurement.')
    number = float(value)
    if number != number or number in (float('inf'), float('-inf')) or number < minimum or number > maximum:
        raise AppError('Enter a valid numeric amount or measurement.')
    return php_round(number, 2)


def wf_quantity(value):
    number = filter_int(value)
    if not number or number < 1 or number > 10000:
        raise AppError('Quantity must be 1\u201310000.')
    return number


def wf_id(key, zero=False):
    value = post().get(key, 0 if zero else None)
    number = filter_int(value)
    if number is None or number < (0 if zero else 1) or number > 2147483647:
        raise AppError('Invalid record reference.')
    return number


def wf_date(value):
    from datetime import datetime
    try:
        parsed = datetime.strptime(value, '%Y-%m-%d') if DATE_RE.match(value) else None
    except (ValueError, TypeError):
        parsed = None
    if parsed is None or parsed.strftime('%Y-%m-%d') != value or value < '2000-01-01' or value > '2099-12-31':
        raise AppError('Enter a valid date.')
    return value


def wf_survey(oid):
    return db.one('SELECT * FROM wf_surveys WHERE order_id=%s', [oid])


def wf_items(oid):
    return db.rows('SELECT i.*,p.name FROM order_items i JOIN products p ON p.id=i.product_id WHERE i.order_id=%s ORDER BY i.id', [oid])


def wf_measurements(oid):
    return db.rows(
        'SELECT m.*,p.name,i.unit_price FROM wf_measurements m JOIN order_items i ON i.id=m.order_item_id '
        'JOIN products p ON p.id=i.product_id WHERE m.order_id=%s AND m.active=1 ORDER BY m.id',
        [oid],
    )


def wf_latest_drawing(mid):
    return db.one('SELECT * FROM wf_drawings WHERE measurement_id=%s ORDER BY revision DESC LIMIT 1', [mid])


def wf_log(oid, u, stage, note):
    db.q('INSERT INTO order_history(order_id,actor_id,stage,note) VALUES (%s,%s,%s,%s)', [oid, u['id'], stage, note])


def wf_invalidate(oid, quote=True):
    db.q("UPDATE wf_drawings SET status='revision_required' WHERE order_id=%s", [oid])
    if quote:
        db.q("UPDATE wf_quotations SET status='revised' WHERE order_id=%s", [oid])
    db.q("UPDATE orders SET stage='order' WHERE id=%s AND stage<>'production'", [oid])


def wf_validate_measurements(raw, items, complete=True):
    if not isinstance(raw, dict) or not raw or len(raw) > 200:
        raise AppError('Add 1\u2013200 measurement groups.')
    by_id = {int(item['id']): item for item in items}
    totals = {}
    result = []
    for row in raw.values():
        if not isinstance(row, dict):
            raise AppError('Invalid measurements.')
        item_id = filter_int(row.get('order_item_id'))
        if not item_id:
            raise AppError('Invalid product reference.')
        if item_id not in by_id:
            raise AppError('Measurement product does not belong to this order.')
        measurement_id = filter_int(row.get('id', 0))
        if measurement_id is None or measurement_id < 0:
            raise AppError('Invalid measurement reference.')
        entry = {'id': measurement_id, 'order_item_id': item_id}
        for key, label in WF_MEASURES.items():
            try:
                value = row.get(key, '')
                entry[key] = wf_number(0 if value == '' else value, 0.1 if complete else 0, 20000)
            except AppError:
                raise AppError(label + ' must be ' + ('greater than zero' if complete else 'zero or greater') +
                               ' and at most 20000 mm. Save Pending to keep incomplete measurements.')
        if complete and (entry['frame_width'] > entry['opening_width'] or entry['frame_height'] > entry['opening_height'] or
                         entry['shutter_width'] > entry['frame_width'] or entry['shutter_height'] > entry['frame_height']):
            raise AppError('Shutter dimensions must fit within the frame, and the frame within the opening.')
        entry['direction'] = wf_text(row.get('direction', 'Left'), 10)
        entry['opening_type'] = wf_text(row.get('opening_type', 'Inward'), 10)
        if entry['direction'] not in ('Left', 'Right') or entry['opening_type'] not in ('Inward', 'Outward'):
            raise AppError('Choose an opening direction and type.')
        entry['location'] = wf_text(row.get('location', ''), 190)
        if complete and entry['location'] == '':
            raise AppError('Location / room is required.')
        entry['quantity'] = wf_quantity(row.get('quantity', 1))
        entry['site_notes'] = wf_text(row.get('site_notes', ''))
        entry['requirements'] = wf_text(row.get('requirements', ''))
        totals[item_id] = totals.get(item_id, 0) + entry['quantity']
        result.append(entry)
    for item_id, item in by_id.items():
        placed = totals.get(item_id, 0)
        if (complete and placed != int(item['quantity'])) or placed > int(item['quantity']):
            raise AppError('Survey group quantities must match each selected product quantity. Split quantities across rooms as needed.')
    return result


def wf_approved_drawings(oid):
    survey = wf_survey(oid)
    if not survey or survey['status'] != 'approved':
        raise AppError('Approve the survey first.')
    measures = wf_measurements(oid)
    if not measures:
        raise AppError('Complete survey measurements first.')
    result = {}
    for measure in measures:
        drawing = wf_latest_drawing(int(measure['id']))
        if not drawing or drawing['status'] != 'approved' or int(drawing['survey_revision']) != int(survey['revision']):
            raise AppError('Every active door measurement needs an approved, current drawing.')
        result[int(measure['id'])] = drawing
    return result


def wf_quote_totals(lines, values):
    subtotal = 0
    for line in lines:
        subtotal += php_round(wf_quantity(line['quantity']) * wf_number(line['unit_price']), 2)
    subtotal = php_round(subtotal, 2)
    discount = wf_number(values.get('discount', 0), 0, subtotal)
    rate = wf_number(values.get('tax_rate', 0), 0, 100)
    installation = wf_number(values.get('installation', 0))
    transport = wf_number(values.get('transport', 0))
    additional = wf_number(values.get('additional', 0))
    taxable = php_round(subtotal - discount + installation + transport + additional, 2)
    tax = php_round(taxable * rate / 100, 2)
    grand = php_round(taxable + tax, 2)
    if grand > 999999999:
        raise AppError('Quotation total exceeds limit.')
    return {
        'subtotal': subtotal,
        'discount': discount,
        'tax_rate': rate,
        'tax': tax,
        'installation': installation,
        'transport': transport,
        'additional': additional,
        'grand_total': grand,
    }


def wf_quote_status(quote):
    if quote['status'] in ('draft', 'sent', 'revised') and str(quote['valid_until']) < today():
        return 'expired'
    return quote['status']


def wf_label(status):
    labels = {
        'completed': 'Survey Completed',
        'prepared': 'Drawing Prepared',
        'sent': 'Sent',
        'revision_required': 'Revision Required',
    }
    return labels.get(status) or ucwords(str(status).replace('_', ' '))


def wf_quote_number(quote):
    return 'ZIV-Q-' + php_date('Y', str(quote['quote_date'])) + '-' + str(int(quote['id'])).zfill(5)


def wf_ready(oid):
    try:
        drawings = wf_approved_drawings(oid)
        quote = db.one('SELECT * FROM wf_quotations WHERE order_id=%s', [oid])
        survey = wf_survey(oid)
        if not quote or quote['status'] != 'approved' or int(quote['survey_revision']) != int(survey['revision']):
            return False
        lines = db.rows('SELECT * FROM wf_quotation_items WHERE quotation_id=%s', [quote['id']])
        if len(lines) != len(drawings):
            return False
        for line in lines:
            if line['measurement_id'] is None or int(line['measurement_id']) not in drawings:
                return False
            if int(drawings[int(line['measurement_id'])]['id']) != int(line['drawing_id'] or 0):
                return False
        return True
    except AppError:
        return False


def wf_production_gate(order):
    if wf_survey(int(order['id'])) and not wf_ready(int(order['id'])):
        raise AppError('Survey, all current drawings and quotation must be approved before production.')


def wf_store_upload(file, kind):
    limit = 10 * 1024 * 1024
    data = read_upload(file, limit)
    if data is None or len(data) < 1 or len(data) > limit:
        raise AppError('Choose a valid upload below 10 MB.')
    original = wf_text(re.split(r'[\\/]', file.filename)[-1], 190)
    extension = original.rsplit('.', 1)[-1].lower() if '.' in original else ''
    allowed = ('jpg', 'jpeg', 'png') if kind == 'survey' else ('jpg', 'jpeg', 'png', 'pdf', 'dxf', 'dwg')
    if extension not in allowed:
        raise AppError('Unsupported attachment format.')
    if extension in ('jpg', 'jpeg', 'png'):
        info = image_info(data)
        if (not info or info[0] not in ('image/jpeg', 'image/png') or info[1] > 10000 or info[2] > 10000 or
                (extension == 'png' and info[0] != 'image/png') or (extension != 'png' and info[0] != 'image/jpeg')):
            raise AppError('Invalid image.')
        mime = info[0]
    elif extension == 'pdf':
        if data[:5] != b'%PDF-':
            raise AppError('Invalid PDF.')
        mime = 'application/pdf'
    else:
        head = data[:512]
        if extension == 'dwg' and not re.match(rb'AC10[0-9]{2}', head):
            raise AppError('Invalid DWG header.')
        if extension == 'dxf' and not head.startswith(b'AutoCAD Binary DXF') and not re.search(rb'\bSECTION\b', head):
            raise AppError('Invalid DXF header.')
        mime = 'application/octet-stream'
    directory = config.WORKFLOW_DIR
    try:
        directory.mkdir(parents=True, exist_ok=True)
        guard = directory / '.htaccess'
        if not guard.is_file():
            guard.write_text('Require all denied\n')
        filename = secrets.token_hex(24) + '.' + extension
        with open(directory / filename, 'wb') as handle:
            handle.write(data)
    except OSError:
        raise AppError('Could not save attachment.')
    return {'filename': filename, 'original_name': original, 'mime': mime, 'bytes': len(data)}


def _insert_sql(table, columns, leading=()):
    names = list(leading) + list(columns)
    return 'INSERT INTO %s(%s) VALUES (%s)' % (table, ','.join(names), ','.join(['%s'] * len(names)))


def wf_action(action, u, transaction=True, initial=False):
    from .quotations import qt_customer_details, qt_quote_rows, qt_template_id
    if not action.startswith('wf_'):
        return False
    oid = wf_id('order_id')
    if transaction:
        db.begin()
    order = db.one('SELECT * FROM orders WHERE id=%s FOR UPDATE', [oid])
    if not order or (not privileged(u) and int(order['salesman_id']) != int(u['id'])):
        raise AppError('Order unavailable.')
    if order['stage'] == 'production' or db.one('SELECT id FROM commissions WHERE order_id=%s', [oid]):
        raise AppError('Released or commissioned orders are locked.')
    survey = wf_survey(oid)
    review = action in ('wf_survey_review', 'wf_drawing_review', 'wf_quote_review')
    if review:
        if not privileged(u):
            raise AppError('Finance or admin approval required.')
    elif not wf_can_edit(u):
        raise AppError('Sales or admin access required.')
    if action == 'wf_start':
        if survey:
            raise AppError('Workflow already started.')
        db.q('INSERT INTO wf_surveys(order_id,updated_by) VALUES (%s,%s)', [oid, u['id']])
        db.q("UPDATE orders SET stage='order' WHERE id=%s", [oid])
        wf_log(oid, u, 'survey', 'Survey / drawing / quotation workflow started.')
    elif not survey:
        raise AppError('Start the survey workflow first.')
    elif action == 'wf_survey':
        if wf_id('revision', True) != int(survey['revision']):
            raise AppError('Survey changed. Reload before saving.')
        status = required('status')
        if status not in ('pending', 'completed'):
            raise AppError('Invalid survey status.')
        raw = post().get('measurements', {})
        if not isinstance(raw, dict):
            raise AppError('Invalid survey measurements.')
        measurements = wf_validate_measurements(raw, wf_items(oid), status == 'completed')
        known = {int(m['id']) for m in db.rows('SELECT id FROM wf_measurements WHERE order_id=%s', [oid])}
        seen = {}
        db.q('UPDATE wf_measurements SET active=0 WHERE order_id=%s', [oid])
        for measurement in measurements:
            record_id = measurement.pop('id')
            if record_id and (record_id not in known or record_id in seen):
                raise AppError('Invalid or duplicate measurement reference.')
            seen[record_id if record_id else -len(seen) - 1] = True
            columns = list(measurement.keys())
            values = [measurement[key] for key in columns]
            if record_id:
                db.q('UPDATE wf_measurements SET ' + ','.join(key + '=%s' for key in columns) + ',active=1 WHERE id=%s AND order_id=%s',
                     values + [record_id, oid])
            else:
                db.q(_insert_sql('wf_measurements', columns, ['order_id']), [oid] + values)
        wf_invalidate(oid, False)
        db.q('UPDATE wf_surveys SET status=%s,revision=revision+1,updated_by=%s WHERE order_id=%s', [status, u['id'], oid])
        wf_log(oid, u, 'survey', 'Survey saved: ' + status + '. Previous drawings / quotation require revision.')
    elif action == 'wf_survey_submit':
        raw = post().get('survey', {})
        items = wf_items(oid)
        if not isinstance(raw, dict) or not items:
            raise AppError('Complete the survey for every item.')
        entries = []
        for item in items:
            row = raw.get(str(item['id']))
            if not isinstance(row, dict):
                raise AppError('Complete the survey for every item.')
            hinge = wf_text(row.get('hinge', ''), 10)
            if hinge not in ('Left', 'Right'):
                raise AppError('Choose a hinge position for every item.')
            sides = {}
            try:
                for key in ('top', 'bottom', 'left', 'right'):
                    sides[key] = wf_number(row.get(key, ''), 0.1, 20000)
            except AppError:
                raise AppError('Enter the top, bottom, left and right measurements (0.1 to 20000 mm) for every item.')
            inner = wf_text(row.get('inner', ''), 80)
            if inner == '':
                raise AppError('Enter the inner measurement for every item.')
            brand_id = filter_int(row.get('brand_id', 0)) or 0
            brand = None
            if brand_id:
                brand = db.one('SELECT id,name FROM door_handle_brands WHERE id=%s AND active=1', [brand_id])
                if not brand:
                    raise AppError('The selected lock brand is no longer available.')
            entries.append((item, sides, inner, hinge, brand))
        existing = {}
        for row in db.rows('SELECT id,order_item_id FROM wf_measurements WHERE order_id=%s ORDER BY id', [oid]):
            existing.setdefault(int(row['order_item_id']), int(row['id']))
        db.q('UPDATE wf_measurements SET active=0 WHERE order_id=%s', [oid])
        for item, sides, inner, hinge, brand in entries:
            length = sides['top']
            height = sides['left']
            values = {
                'opening_width': length, 'opening_height': height, 'wall_thickness': 0,
                'frame_width': length, 'frame_height': height, 'shutter_width': length, 'shutter_height': height,
                'direction': hinge, 'opening_type': 'Inward', 'location': 'Survey completed', 'quantity': int(item['quantity']),
                'side_top': '%g' % sides['top'], 'side_bottom': '%g' % sides['bottom'],
                'side_left': '%g' % sides['left'], 'side_right': '%g' % sides['right'],
                'inner_detail': inner,
                'handle_brand_id': int(brand['id']) if brand else None, 'handle_brand': brand['name'] if brand else None,
            }
            columns = list(values.keys())
            params = [values[key] for key in columns]
            record_id = existing.get(int(item['id']))
            if record_id:
                db.q('UPDATE wf_measurements SET ' + ','.join(key + '=%s' for key in columns) + ',active=1 WHERE id=%s AND order_id=%s',
                     params + [record_id, oid])
            else:
                db.q(_insert_sql('wf_measurements', ['order_item_id'] + columns, ['order_id']), [oid, item['id']] + params)
        wf_invalidate(oid, False)
        db.q("UPDATE wf_surveys SET status='completed',revision=revision+1,updated_by=%s WHERE order_id=%s", [u['id'], oid])
        wf_log(oid, u, 'survey', 'Survey submitted for %d item(s).' % len(entries))
        session['quote_created_order'] = oid
    elif action == 'wf_survey_review':

        status = required('status')
        if status not in ('approved', 'revision_required') or survey['status'] not in ('completed', 'approved') or \
                wf_id('revision', True) != int(survey['revision']):
            raise AppError('Review the current completed survey.')
        note = required('note', 2000)
        if status == 'revision_required':
            wf_invalidate(oid)
        db.q('UPDATE wf_surveys SET status=%s,updated_by=%s WHERE order_id=%s', [status, u['id'], oid])
        wf_log(oid, u, 'survey', 'Survey ' + status + ': ' + note)
    elif action == 'wf_drawing':
        if survey['status'] not in ('completed', 'approved'):
            raise AppError('Complete the survey first.')
        measurement = db.one(
            'SELECT m.*,p.name FROM wf_measurements m JOIN order_items i ON i.id=m.order_item_id JOIN products p ON p.id=i.product_id '
            'WHERE m.id=%s AND m.order_id=%s AND m.active=1',
            [wf_id('measurement_id'), oid],
        )
        if not measurement:
            raise AppError('Measurement unavailable.')
        labels = post().get('labels', {})
        xs = post().get('xs', {})
        ys = post().get('ys', {})
        if not isinstance(labels, dict) or not isinstance(xs, dict) or not isinstance(ys, dict) or len(labels) > 8:
            raise AppError('Use up to eight annotations.')
        annotations = []
        for key, text in labels.items():
            text = wf_text(text, 100)
            if text != '':
                annotations.append({'text': text, 'x': wf_number(xs.get(key, 50), 0, 100), 'y': wf_number(ys.get(key, 50), 0, 100)})
        last = wf_latest_drawing(int(measurement['id']))
        version = int(last['revision']) + 1 if last else 1
        payload = {
            'measurement': measurement,
            'notes': val('drawing_notes', 2000),
            'annotations': annotations,
            'order_id': oid,
            'survey_revision': int(survey['revision']),
            'revision': version,
        }
        db.q("UPDATE wf_drawings SET status='revision_required' WHERE measurement_id=%s", [measurement['id']])
        db.q("UPDATE wf_quotations SET status='revised' WHERE order_id=%s", [oid])
        db.q("UPDATE orders SET stage='order' WHERE id=%s", [oid])
        db.q('INSERT INTO wf_drawings(order_id,measurement_id,revision,survey_revision,payload,created_by) VALUES (%s,%s,%s,%s,%s,%s)',
             [oid, measurement['id'], version, survey['revision'], json.dumps(payload, default=str), u['id']])
        wf_log(oid, u, 'drawing', 'Generated measurement #%s drawing revision %s.' % (measurement['id'], version))
    elif action in ('wf_drawing_send', 'wf_drawing_review'):
        drawing = db.one('SELECT * FROM wf_drawings WHERE id=%s AND order_id=%s', [wf_id('drawing_id', True), oid])
        if not drawing or int(drawing['survey_revision']) != int(survey['revision']) or \
                int(wf_latest_drawing(int(drawing['measurement_id']))['id']) != int(drawing['id']):
            raise AppError('Use the latest drawing for the current survey.')
        status = 'sent' if action == 'wf_drawing_send' else required('status')
        if action == 'wf_drawing_send' and drawing['status'] != 'prepared':
            raise AppError('Generate a prepared drawing first.')
        if action == 'wf_drawing_review' and (status not in ('approved', 'revision_required') or drawing['status'] not in ('sent', 'approved')):
            raise AppError('Drawing must be sent for approval first.')
        if status == 'approved' and survey['status'] != 'approved':
            raise AppError('Approve the survey first.')
        if status == 'revision_required':
            db.q("UPDATE wf_quotations SET status='revised' WHERE order_id=%s", [oid])
            db.q("UPDATE orders SET stage='order' WHERE id=%s", [oid])
        db.q('UPDATE wf_drawings SET status=%s WHERE id=%s', [status, drawing['id']])
        wf_log(oid, u, 'drawing', 'Drawing #%s %s: %s' % (drawing['id'], status, required('note', 2000) if review else 'Sent for approval.'))
    elif action == 'wf_quote':
        _wf_quote(oid, u, order, survey, qt_customer_details, qt_quote_rows, qt_template_id, initial)
    elif action == 'wf_quote_review':
        quote = db.one('SELECT * FROM wf_quotations WHERE order_id=%s', [oid])
        if not quote or wf_id('revision', True) != int(quote['revision']):
            raise AppError('Review the current quotation.')
        effective = wf_quote_status(quote)
        status = required('status')
        if effective == 'expired':
            raise AppError('Quotation expired. Revise validity before sending or approving.')
        if action == 'wf_quote_review' and status == 'approved':
            current = wf_approved_drawings(oid)
            quote_lines = db.rows('SELECT * FROM wf_quotation_items WHERE quotation_id=%s', [quote['id']])
            if int(quote['survey_revision']) != int(survey['revision']) or len(quote_lines) != len(current):
                raise AppError('Regenerate the quotation for the current survey and drawings.')
            for line in quote_lines:
                if line['measurement_id'] is None or int(line['measurement_id']) not in current or \
                        int(current[int(line['measurement_id'])]['id']) != int(line['drawing_id'] or 0):
                    raise AppError('A drawing changed. Save a revised quotation first.')
        if effective != 'sent' or status not in ('approved', 'rejected'):
            raise AppError('Only sent quotations can be approved or rejected.')
        db.q('UPDATE wf_quotations SET status=%s,updated_by=%s WHERE id=%s', [status, u['id'], quote['id']])
        if status == 'approved':
            if float(order['advance']) > float(quote['grand_total']):
                raise AppError('Quoted total cannot be less than advance already collected.')
            db.q("UPDATE orders SET stage='finance',total=%s WHERE id=%s", [quote['grand_total'], oid])
            by_item = {}
            for line in db.rows('SELECT order_item_id,quantity,line_total FROM wf_quotation_items WHERE quotation_id=%s', [quote['id']]):
                key = int(line['order_item_id'])
                by_item[key] = by_item.get(key, 0) + float(line['line_total'])
            for item in wf_items(oid):
                db.q('UPDATE order_items SET unit_price=%s WHERE id=%s',
                     [php_round(by_item.get(int(item['id']), 0) / int(item['quantity']), 2), item['id']])
        wf_log(oid, u, 'quotation', 'Quotation #%s %s: %s' % (quote['id'], status, required('note', 2000)))
    elif action == 'wf_upload':
        kind = required('kind', 15)
        if kind not in ('survey', 'drawing'):
            raise AppError('Invalid attachment type.')
        drawing_id = wf_id('drawing_id', True)
        if drawing_id and not db.one('SELECT id FROM wf_drawings WHERE id=%s AND order_id=%s', [drawing_id, oid]):
            raise AppError('Drawing unavailable.')
        stored = wf_store_upload(files().get('attachment'), kind)
        try:
            db.q('INSERT INTO wf_attachments(order_id,kind,drawing_id,filename,original_name,mime,bytes,uploaded_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                 [oid, kind, drawing_id or None, stored['filename'], stored['original_name'], stored['mime'], stored['bytes'], u['id']])
            wf_log(oid, u, 'survey' if kind == 'survey' else 'drawing', 'Attached ' + stored['original_name'])
            db.commit()
        except Exception:
            try:
                (config.WORKFLOW_DIR / stored['filename']).unlink()
            except OSError:
                pass
            raise
        return True
    else:
        raise AppError('Unknown workflow action.')
    if transaction:
        db.commit()
    return True


def _wf_quote(oid, u, order, survey, qt_customer_details, qt_quote_rows, qt_template_id, initial=False):
    data = post()
    quote = db.one('SELECT * FROM wf_quotations WHERE order_id=%s', [oid])
    if wf_id('revision', True) != (int(quote['revision']) if quote else 0):
        raise AppError('Quotation changed. Reload before saving.')
    raw = data.get('quote_items', {})
    if not isinstance(raw, dict):
        raise AppError('Invalid quotation lines.')
    measurements = qt_quote_rows(oid)
    if not initial and any(not int(row['id']) or float(row.get('opening_width') or 0) <= 0 for row in measurements):
        raise AppError('Complete the survey for every item before submitting the quotation.')
    if len(raw) != len(measurements):
        raise AppError('Quote every selected product / door group.')
    lines = []
    quantity_changes = {}
    item_quantities = {}
    for measurement in measurements:
        key = measurement['quote_key']
        line = raw.get(key)
        if not isinstance(line, dict):
            raise AppError('Missing quotation line.')
        quantity = wf_quantity(line.get('quantity'))
        item_id = int(measurement['order_item_id'])
        item_quantities[item_id] = item_quantities.get(item_id, 0) + quantity
        if quantity != int(measurement['quantity']) and measurement['id']:
            quantity_changes[int(measurement['id'])] = quantity
        measurement['quantity'] = quantity
        drawing = wf_latest_drawing(int(measurement['id'])) if measurement['id'] else None
        drawing_id = int(drawing['id']) if drawing and drawing['status'] == 'approved' and int(drawing['survey_revision']) == int(survey['revision']) else None
        price = wf_number(line.get('unit_price', 0))
        lines.append({
            'measurement_id': int(measurement['id']) or None,
            'order_item_id': item_id,
            'drawing_id': drawing_id,
            'quantity': quantity,
            'unit_price': price,
            'line_total': php_round(quantity * price, 2),
            'snapshot': json.dumps(measurement, default=str),
        })
    calculation = dict(data)
    entered_discount = wf_number(data.get('discount', 0))
    discount_type = wf_text(data.get('discount_type', 'amount'), 10)
    if discount_type not in ('amount', 'percent'):
        raise AppError('Invalid discount type.')
    if discount_type == 'percent':
        if entered_discount > 100:
            raise AppError('Discount percentage must be 0\u2013100.')
        goods = sum(line['line_total'] for line in lines)
        calculation['discount'] = php_round(goods * entered_discount / 100, 2)
    amounts = wf_quote_totals(lines, calculation)
    date = wf_date(wf_text(data.get('quote_date', today()), 10))
    until = wf_date(wf_text(data.get('valid_until', add_days(today(), 30)), 10))
    if until < date:
        raise AppError('Quotation validity must be on or after its date.')
    if quantity_changes:
        for quantity in item_quantities.values():
            if quantity > 10000:
                raise AppError('Total quantity per product cannot exceed 10000.')
        for measurement_id, quantity in quantity_changes.items():
            db.q('UPDATE wf_measurements SET quantity=%s WHERE id=%s AND order_id=%s', [quantity, measurement_id, oid])
        for item_id, quantity in item_quantities.items():
            db.q('UPDATE order_items SET quantity=%s WHERE id=%s AND order_id=%s', [quantity, item_id, oid])
        wf_invalidate(oid)
        db.q("UPDATE wf_surveys SET revision=revision+1,status='completed',updated_by=%s WHERE order_id=%s", [u['id'], oid])
        survey['revision'] = int(survey['revision']) + 1
        wf_log(oid, u, 'survey', 'Quotation quantities changed. Survey quantities updated; new survey and drawing approvals are required.')
    version = int(quote['revision']) + 1 if quote else 1
    values = {
        'survey_revision': survey['revision'],
        'status': 'sent',
        'quote_date': date,
        'valid_until': until,
    }
    values.update(amounts)
    values.update({
        'terms': val('terms', 5000),
        'payment_terms': val('payment_terms', 2000),
        'delivery': val('delivery', 1000),
        'notes': val('quote_notes', 3000),
        'company_snapshot': json.dumps(config.COMPANY or {'name': 'ZIVOC Doors'}),
        'updated_by': u['id'],
        'customer_details': json.dumps(qt_customer_details(data, order)),
        'discount_type': discount_type,
        'discount_value': entered_discount,
        'template_id': qt_template_id(data.get('template_id')),
    })
    for quantity in item_quantities.values():
        if quantity > 10000:
            raise AppError('Total quantity per product cannot exceed 10000.')
    for item_id, quantity in item_quantities.items():
        db.q('UPDATE order_items SET quantity=%s WHERE id=%s AND order_id=%s', [quantity, item_id, oid])
    keys = list(values.keys())
    params = [values[key] for key in keys]
    if quote:
        db.q('UPDATE wf_quotations SET revision=%s,' + ','.join(key + '=%s' for key in keys) + ' WHERE id=%s', [version] + params + [quote['id']])
        qid = int(quote['id'])
        db.q('DELETE FROM wf_quotation_items WHERE quotation_id=%s', [qid])
    else:
        db.q(_insert_sql('wf_quotations', keys, ['order_id']), [oid] + params)
        qid = int(db.insert_id())
    for line in lines:
        columns = list(line.keys())
        db.q(_insert_sql('wf_quotation_items', columns, ['quotation_id']), [qid] + [line[column] for column in columns])
    saved = db.one('SELECT * FROM wf_quotations WHERE id=%s', [qid])
    customer = {key: order.get(key) for key in ('customer', 'phone', 'address', 'lead_id')}
    db.q('INSERT INTO wf_quotation_revisions(quotation_id,revision,payload,created_by) VALUES (%s,%s,%s,%s)',
         [qid, version, json.dumps({'quote': saved, 'items': lines, 'customer': customer}, default=str), u['id']])
    db.q("UPDATE orders SET stage='order' WHERE id=%s", [oid])
    wf_log(oid, u, 'quotation', 'Quotation #%s revision %s %s.' % (qid, version, 'created' if initial else 'submitted and sent'))
    session['quote_to_list'] = True
