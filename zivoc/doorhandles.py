import secrets

from . import config, db
from .core import AppError, files
from .helpers import require_admin, required, to_int, val
from .uploads import image_info, read_upload

IMAGE_TYPES = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}


def dh_brands(active_only=False):
    sql = 'SELECT * FROM door_handle_brands' + (' WHERE active=1' if active_only else '') + ' ORDER BY name'
    return db.rows(sql)


def _brand_image():
    limit = 3 * 1024 * 1024
    data = read_upload(files().get('image'), limit)
    if data is None:
        return None
    if not data or len(data) > limit:
        raise AppError('Lock brand image must be below 3 MB.')
    info = image_info(data)
    if not info or info[0] not in IMAGE_TYPES or info[1] > 6000 or info[2] > 6000:
        raise AppError('Use a valid JPG, PNG or WebP image.')
    name = secrets.token_hex(24) + '.' + IMAGE_TYPES[info[0]]
    config.BRAND_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(config.BRAND_DIR / name, 'wb') as handle:
            handle.write(data)
    except OSError:
        raise AppError('Unable to save lock brand image.')
    return name


def _remove_image(name):
    if not name:
        return
    try:
        (config.BRAND_DIR / name).unlink()
    except OSError:
        pass


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
        raise AppError('A lock brand with this name already exists.')
    existing = None
    if brand_id:
        existing = db.one('SELECT id,image FROM door_handle_brands WHERE id=%s', [brand_id])
        if not existing:
            raise AppError('Lock brand unavailable.')
    image = _brand_image()
    if existing:
        if image:
            db.q('UPDATE door_handle_brands SET name=%s,company=%s,details=%s,active=%s,image=%s WHERE id=%s', [name, company, details, active, image, brand_id])
            _remove_image(existing['image'])
        else:
            db.q('UPDATE door_handle_brands SET name=%s,company=%s,details=%s,active=%s WHERE id=%s', [name, company, details, active, brand_id])
        db.q('UPDATE wf_measurements SET handle_brand=%s WHERE handle_brand_id=%s', [name, brand_id])
    else:
        db.q('INSERT INTO door_handle_brands(name,company,details,active,image,created_by) VALUES (%s,%s,%s,%s,%s,%s)', [name, company, details, active, image, u['id']])
    return True
