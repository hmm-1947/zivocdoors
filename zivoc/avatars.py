import re
import secrets
import time
from urllib.parse import quote

import requests

from . import config, db
from .core import AppError, files
from .helpers import reset_user_cache
from .uploads import image_info, read_upload

TYPES = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}
MIMES = {ext: mime for mime, ext in TYPES.items()}
LIMIT = 5 * 1024 * 1024
REFRESH_SECONDS = 300
_checked = {}


def _headers():
    return {'Authorization': 'token ' + config.ERP_TOKEN, 'Accept': 'application/json'}


def valid_ext(data):
    if not data or len(data) > LIMIT:
        return None
    info = image_info(data)
    if not info or info[0] not in TYPES or info[1] > 6000 or info[2] > 6000:
        return None
    return TYPES[info[0]]


def _write(user_id, data, ext):
    name = '%d-%s.%s' % (user_id, secrets.token_hex(8), ext)
    config.AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.AVATAR_DIR / name, 'wb') as handle:
        handle.write(data)
    return name


def _remove(name):
    if not name:
        return
    try:
        (config.AVATAR_DIR / re.split(r'[\\/]', name)[-1]).unlink()
    except OSError:
        pass


def _download(src):
    if src.startswith('/') and not src.startswith('//'):
        url = config.ERP_BASE_URL + src
    elif src.startswith(config.ERP_BASE_URL + '/'):
        url = src
    else:
        return None
    try:
        response = requests.get(url, headers=_headers(), timeout=(5, 20))
    except requests.RequestException:
        return None
    if response.status_code != 200 or len(response.content) > LIMIT:
        return None
    return response.content


def pull(record, erp_image):
    src = str(erp_image or '').strip()[:255]
    current = record.get('avatar_src') or ''
    if src == current:
        return False
    if not src:
        if current:
            _remove(record.get('avatar'))
            db.q('UPDATE users SET avatar=NULL,avatar_src=NULL WHERE id=%s', [record['id']])
            return True
        return False
    data = _download(src)
    ext = valid_ext(data) if data else None
    if not ext:
        return False
    name = _write(int(record['id']), data, ext)
    db.q('UPDATE users SET avatar=%s,avatar_src=%s WHERE id=%s', [name, src, record['id']])
    _remove(record.get('avatar'))
    return True


def refresh(u):
    code = u.get('employee_id')
    if not code or not config.ERP_TOKEN:
        return False
    now = time.time()
    if now - _checked.get(int(u['id']), 0) < REFRESH_SECONDS:
        return False
    _checked[int(u['id'])] = now
    try:
        response = requests.get(config.ERP_BASE_URL + '/api/resource/Employee/' + quote(str(code), safe=''), headers=_headers(), timeout=(3, 8))
        data = response.json()
    except (requests.RequestException, ValueError):
        return False
    if response.status_code != 200 or not isinstance(data, dict) or not isinstance(data.get('data'), dict):
        return False
    try:
        return pull(u, data['data'].get('image'))
    except Exception:
        return False


def _push(code, data, ext):
    if not config.ERP_TOKEN:
        raise AppError('ERP token is not configured. Picture not changed.')
    base = config.ERP_BASE_URL
    filename = 'avatar-%s-%s.%s' % (re.sub(r'[^A-Za-z0-9]', '', str(code))[:30], secrets.token_hex(3), ext)
    try:
        response = requests.post(
            base + '/api/method/upload_file', headers=_headers(), files={'file': (filename, data, MIMES[ext])},
            data={'is_private': '1', 'doctype': 'Employee', 'docname': code, 'fieldname': 'image', 'folder': 'Home/Attachments'}, timeout=(10, 40))
        body = response.json()
    except (requests.RequestException, ValueError):
        raise AppError('Could not reach ERP. Picture not changed.')
    message = body.get('message') if isinstance(body, dict) else None
    url = message.get('file_url') if isinstance(message, dict) else None
    if response.status_code != 200 or not url:
        raise AppError('ERP rejected the picture. Picture not changed.')
    employee_url = base + '/api/resource/Employee/' + quote(str(code), safe='')
    try:
        check = requests.get(employee_url, headers=_headers(), timeout=(5, 15))
        current = ((check.json() or {}).get('data') or {}).get('image')
        if current != url:
            update = requests.put(employee_url, headers=_headers(), json={'image': url}, timeout=(5, 20))
            if update.status_code != 200:
                raise AppError('ERP could not set the employee picture. Picture not changed.')
    except (requests.RequestException, ValueError):
        raise AppError('Could not confirm the picture in ERP. Picture not changed.')
    return url


def avatar_upload(u):
    data = read_upload(files().get('avatar'), LIMIT)
    if data is None:
        raise AppError('Choose a picture to upload.')
    ext = valid_ext(data)
    if not ext:
        raise AppError('Use a JPG, PNG or WebP picture below 5 MB.')
    src = _push(u['employee_id'], data, ext) if u.get('employee_id') else None
    name = _write(int(u['id']), data, ext)
    db.q('UPDATE users SET avatar=%s,avatar_src=%s WHERE id=%s', [name, src, u['id']])
    _remove(u.get('avatar'))
    _checked[int(u['id'])] = time.time()
    reset_user_cache()
