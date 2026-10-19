import json
import re
from urllib.parse import urlsplit

import requests

from . import config, db
from .core import AppError

UNSAFE_PATH_RE = re.compile(r'[\x00-\x20\x7f\\]')
SCHEME_RE = re.compile(r'^[a-z][a-z0-9+.-]*:', re.I)
DEFAULT_PRICE = 7500.0


def ensure_price_table():
    db.q(
        'CREATE TABLE IF NOT EXISTS erp_prices ('
        'item_code VARCHAR(190) PRIMARY KEY, '
        'price DECIMAL(12,2) NOT NULL)'
    )


def price_overrides():
    try:
        ensure_price_table()
        return {row['item_code']: float(row['price']) for row in db.rows('SELECT item_code,price FROM erp_prices')}
    except Exception:
        return {}


def set_price(code, price):
    ensure_price_table()
    db.q(
        'INSERT INTO erp_prices(item_code,price) VALUES (%s,%s) ON DUPLICATE KEY UPDATE price=VALUES(price)',
        [code, price],
    )
    try:
        db.q(
            'UPDATE products SET price=%s WHERE id=(SELECT product_id FROM erp_products WHERE item_code=%s)',
            [price, code],
        )
    except Exception:
        pass


def product_image_origin():
    parts = urlsplit(str(config.PRODUCT_IMAGE_BASE_URL or ''))
    if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        return ''
    port = ':%d' % parts.port if parts.port else ''
    return 'https://' + parts.hostname + port


def product_image_url(path):
    if not isinstance(path, str):
        return ''
    path = path.strip()
    origin = product_image_origin()
    if path == '' or origin == '' or UNSAFE_PATH_RE.search(path) or path.startswith('//'):
        return ''
    if SCHEME_RE.match(path):
        parts = urlsplit(path)
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
            return ''
        port = ':%d' % parts.port if parts.port else ''
        image_origin = 'https://' + parts.hostname + port
        return path if origin.lower() == image_origin.lower() else ''
    return config.PRODUCT_IMAGE_BASE_URL.rstrip('/') + '/' + path.lstrip('/')


def catalog():
    token = config.ERP_TOKEN
    if not token:
        raise AppError('Product API is not configured.')
    params = {
        'filters': json.dumps([
            ['item_group', '=', 'selling item'],
            ['is_sales_item', '=', 1],
            ['disabled', '=', 0],
            ['item_group', '!=', ''],
        ]),
        'fields': json.dumps(['name', 'item_name', 'item_group', 'stock_uom', 'image']),
        'limit_page_length': 1000,
    }
    try:
        response = requests.get(
            config.ERP_BASE_URL + '/api/resource/Item',
            params=params,
            headers={'Authorization': 'token ' + token, 'Accept': 'application/json'},
            timeout=(10, 30),
        )
    except requests.RequestException:
        raise AppError('Products could not be loaded. Please try again.')
    if response.status_code != 200:
        raise AppError('Products could not be loaded. Please try again.')
    try:
        data = response.json()
    except ValueError:
        raise AppError('Invalid product API response.')
    if not isinstance(data, dict) or not isinstance(data.get('data'), list):
        raise AppError('Invalid product API response.')
    prices = price_overrides()
    items = {}
    for item in data['data']:
        if not isinstance(item, dict) or not isinstance(item.get('name'), str) or item['name'] == '':
            raise AppError('Invalid product API response.')
        group = str(item.get('item_group') or '').strip()
        if group == '':
            continue
        uom = item.get('stock_uom') or ''
        items[item['name']] = {
            'code': item['name'],
            'name': item.get('item_name') or item['name'],
            'item_group': group,
            'stock_uom': uom,
            'description': group + ' \u00b7 ' + str(uom),
            'price': prices.get(item['name'], DEFAULT_PRICE),
            'image': product_image_url(item.get('image')),
        }
    return items


def local_product(item):
    db.q(
        'CREATE TABLE IF NOT EXISTS erp_products ('
        'item_code VARCHAR(190) PRIMARY KEY, '
        'product_id INT NOT NULL UNIQUE, '
        'FOREIGN KEY(product_id) REFERENCES products(id))'
    )
    existing = db.one('SELECT product_id FROM erp_products WHERE item_code=%s', [item['code']])
    if existing:
        return int(existing['product_id'])
    db.q(
        'INSERT INTO products(name, description, price, active) VALUES (%s,%s,%s,1)',
        [item['name'][:150], item['description'], item['price']],
    )
    product_id = db.insert_id()
    db.q('INSERT INTO erp_products(item_code, product_id) VALUES (%s,%s)', [item['code'], product_id])
    return product_id
