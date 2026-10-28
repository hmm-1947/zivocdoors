import json

from . import config, db
from .core import AppError
from .helpers import require_admin, to_int, val
from .workflow import wf_quote_number

ENTITIES = ('lead', 'order', 'quotation')


def ensure_log_table():
    db.q(
        'CREATE TABLE IF NOT EXISTS deletion_logs (id INT AUTO_INCREMENT PRIMARY KEY, entity_type VARCHAR(20) NOT NULL, '
        'entity_id INT NOT NULL, label VARCHAR(255) NOT NULL, customer VARCHAR(190) NULL, deleted_by INT NULL, '
        'deleted_by_name VARCHAR(120) NOT NULL, summary TEXT NULL, snapshot LONGTEXT NULL, '
        'created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, INDEX(entity_type), INDEX(created_at))'
    )


def _edges():
    result = {}
    for row in db.rows(
        'SELECT k.TABLE_NAME child, k.COLUMN_NAME child_col, k.REFERENCED_TABLE_NAME parent, k.REFERENCED_COLUMN_NAME parent_col, '
        '(SELECT c.IS_NULLABLE FROM information_schema.COLUMNS c WHERE c.TABLE_SCHEMA=k.TABLE_SCHEMA AND c.TABLE_NAME=k.TABLE_NAME AND c.COLUMN_NAME=k.COLUMN_NAME) nullable '
        'FROM information_schema.KEY_COLUMN_USAGE k WHERE k.TABLE_SCHEMA=DATABASE() AND k.REFERENCED_TABLE_NAME IS NOT NULL'
    ):
        result.setdefault(row['parent'], []).append(row)
    return result


def _purge(table, column, values, edges, counts, files, seen):
    values = [v for v in values if v is not None]
    if not values:
        return
    key = (table, column, tuple(sorted(str(v) for v in values)))
    if key in seen:
        return
    seen.add(key)
    marks = ','.join(['%s'] * len(values))
    for edge in edges.get(table, []):
        found = [r['v'] for r in db.rows('SELECT DISTINCT `%s` v FROM `%s` WHERE `%s` IN (%s)' % (edge['parent_col'], table, column, marks), values)]
        _purge(edge['child'], edge['child_col'], found, edges, counts, files, seen)
    if table == 'wf_attachments':
        files.extend(r['filename'] for r in db.rows('SELECT filename FROM wf_attachments WHERE `%s` IN (%s)' % (column, marks), values))
    cursor = db.q('DELETE FROM `%s` WHERE `%s` IN (%s)' % (table, column, marks), values)
    if cursor.rowcount:
        counts[table] = counts.get(table, 0) + cursor.rowcount
    cursor.close()


def _remove_files(files):
    for name in files:
        try:
            (config.WORKFLOW_DIR / name.replace('\\', '/').split('/')[-1]).unlink()
        except OSError:
            pass


def _record(kind, record_id):
    if kind == 'lead':
        row = db.one('SELECT l.*,u.name salesman FROM leads l JOIN users u ON u.id=l.salesman_id WHERE l.id=%s', [record_id])
        if not row:
            raise AppError('Lead unavailable.')
        from .leads import lead_number
        return row, lead_number(row), row['name'], ('leads', 'id')
    if kind == 'order':
        row = db.one('SELECT o.*,u.name salesman FROM orders o JOIN users u ON u.id=o.salesman_id WHERE o.id=%s', [record_id])
        if not row:
            raise AppError('Order unavailable.')
        return row, 'Order #%04d' % int(row['id']), row['customer'], ('orders', 'id')
    row = db.one('SELECT q.*,o.customer,o.phone FROM wf_quotations q JOIN orders o ON o.id=q.order_id WHERE q.id=%s', [record_id])
    if not row:
        raise AppError('Quotation unavailable.')
    return row, 'Quotation ' + str(wf_quote_number(row)), row['customer'], ('wf_quotations', 'id')


def delete_record(kind, record_id, u):
    require_admin(u)
    if kind not in ENTITIES:
        raise AppError('Invalid record.')
    row, label, customer, (table, column) = _record(kind, record_id)
    counts = {}
    files = []
    db.begin()
    edges = _edges()
    if kind == 'lead':
        for edge in edges.get('leads', []):
            if edge['nullable'] != 'YES':
                continue
            if edge['child'] == 'reminders':
                cursor = db.q('DELETE FROM reminders WHERE lead_id=%s AND order_id IS NULL', [record_id])
                if cursor.rowcount:
                    counts['reminders'] = cursor.rowcount
                cursor.close()
            cursor = db.q('UPDATE `%s` SET `%s`=NULL WHERE `%s`=%%s' % (edge['child'], edge['child_col'], edge['child_col']), [record_id])
            if cursor.rowcount:
                counts['unlinked_' + edge['child']] = cursor.rowcount
            cursor.close()
        edges['leads'] = [edge for edge in edges.get('leads', []) if edge['nullable'] != 'YES']
    _purge(table, column, [record_id], edges, counts, files, set())
    db.q(
        'INSERT INTO deletion_logs(entity_type,entity_id,label,customer,deleted_by,deleted_by_name,summary,snapshot) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
        [kind, record_id, label[:255], (customer or '')[:190], u['id'], u['name'][:120], json.dumps(counts), json.dumps(row, default=str)],
    )
    db.commit()
    _remove_files(files)


def deletion_action(action, u):
    kind = {'delete_lead': 'lead', 'delete_order': 'order', 'delete_quotation': 'quotation'}.get(action)
    if not kind:
        return False
    require_admin(u)
    delete_record(kind, to_int(val('id')), u)
    return True


def log_listing(args):
    where = ['1=1']
    params = []
    kind = args.get('type', '')
    if kind in ENTITIES:
        where.append('entity_type=%s')
        params.append(kind)
    else:
        kind = ''
    search = args.get('search', '').strip()[:100]
    if search:
        where.append('(label LIKE %s OR customer LIKE %s OR deleted_by_name LIKE %s)')
        params.extend(['%' + search + '%'] * 3)
    limit = args.get('limit', '100')
    if limit not in ('100', '250', '500', '1000'):
        limit = '100'
    clause = ' AND '.join(where)
    count = int(db.one('SELECT COUNT(*) n FROM deletion_logs WHERE ' + clause, params)['n'])
    size = int(limit)
    pages = max(1, -(-count // size))
    page_no = min(max(1, to_int(args.get('p', 1), 1)), pages)
    rows = db.rows('SELECT * FROM deletion_logs WHERE ' + clause + ' ORDER BY id DESC LIMIT %d OFFSET %d' % (size, (page_no - 1) * size), params)
    for row in rows:
        try:
            row['counts'] = json.loads(row['summary'] or '{}')
        except ValueError:
            row['counts'] = {}
        try:
            row['data'] = json.dumps(json.loads(row['snapshot'] or '{}'), indent=2)
        except ValueError:
            row['data'] = row['snapshot'] or ''
    return {'logs': rows, 'd_type': kind, 'd_search': search, 'd_limit': limit, 'd_count': count, 'd_page': page_no, 'd_pages': pages, 'd_offset': (page_no - 1) * size}
