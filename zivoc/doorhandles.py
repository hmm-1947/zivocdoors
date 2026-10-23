from . import db
from .core import AppError
from .helpers import require_admin, required, to_int, val


def dh_brands(active_only=False):
    sql = 'SELECT * FROM door_handle_brands' + (' WHERE active=1' if active_only else '') + ' ORDER BY name'
    return db.rows(sql)


def dh_action(action, u):
    if action != 'dh_brand':
        return False
    require_admin(u)
    brand_id = to_int(val('brand_id')) or 0
    name = required('name', 150)
    company = val('company', 190)
    details = val('details', 3000)
    active = 0 if val('active') == '0' else 1
    duplicate = db.one('SELECT id FROM door_handle_brands WHERE LOWER(name)=LOWER(%s) AND id<>%s', [name, brand_id])
    if duplicate:
        raise AppError('A door handle brand with this name already exists.')
    if brand_id:
        if not db.one('SELECT id FROM door_handle_brands WHERE id=%s', [brand_id]):
            raise AppError('Door handle brand unavailable.')
        db.q('UPDATE door_handle_brands SET name=%s,company=%s,details=%s,active=%s WHERE id=%s', [name, company, details, active, brand_id])
        db.q('UPDATE wf_measurements SET handle_brand=%s WHERE handle_brand_id=%s', [name, brand_id])
    else:
        db.q('INSERT INTO door_handle_brands(name,company,details,active,created_by) VALUES (%s,%s,%s,%s,%s)', [name, company, details, active, u['id']])
    return True
