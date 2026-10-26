import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def _env(name, default=''):
    return os.environ.get(name, default)


def _bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


COMPANY = {
    'name': _env('ZIVOC_COMPANY_NAME', 'ZIVOC Doors'),
    'address': _env('ZIVOC_COMPANY_ADDRESS'),
    'phone': _env('ZIVOC_COMPANY_PHONE'),
    'email': _env('ZIVOC_COMPANY_EMAIL'),
    'gstin': _env('ZIVOC_COMPANY_GSTIN'),
}

PRODUCT_IMAGE_BASE_URL = _env('ZIVOC_PRODUCT_IMAGE_BASE_URL', 'https://zivoc.tech/')
ERP_BASE_URL = _env('ZIVOC_ERP_BASE_URL', 'https://zivoc.tech').rstrip('/')
ERP_TOKEN = _env('ZIVOC_ERP_TOKEN')

DB_HOST = _env('ZIVOC_DB_HOST', 'localhost')
DB_PORT = int(_env('ZIVOC_DB_PORT', '3306') or 3306)
DB_NAME = _env('ZIVOC_DB_NAME')
DB_USER = _env('ZIVOC_DB_USER')
DB_PASSWORD = _env('ZIVOC_DB_PASSWORD')

TIMEZONE = _env('ZIVOC_TIMEZONE', 'Asia/Kolkata')
IMPORT_TOKEN = _env('ZIVOC_IMPORT_TOKEN')

INSTALL_ENABLED = _bool('ZIVOC_INSTALL_ENABLED', False)
INSTALL_KEY = _env('ZIVOC_INSTALL_KEY')

STORAGE_DIR = Path(_env('ZIVOC_STORAGE_DIR', str(BASE_DIR / 'storage')))
SELFIE_DIR = STORAGE_DIR / 'selfies'
WORKFLOW_DIR = STORAGE_DIR / 'workflow'
BRAND_DIR = STORAGE_DIR / 'brands'
SESSION_DIR = STORAGE_DIR / 'sessions'

SESSION_LIFETIME_SECONDS = int(_env('ZIVOC_SESSION_LIFETIME', str(60 * 60 * 24 * 7)))
COOKIE_SECURE = _env('ZIVOC_COOKIE_SECURE', 'auto').lower()
TRUST_PROXY = _bool('ZIVOC_TRUST_PROXY', False)
MAX_UPLOAD_BYTES = 12 * 1024 * 1024

POS_DB_HOST = _env('ZIVOC_POS_DB_HOST', 'localhost')
POS_DB_NAME = _env('ZIVOC_POS_DB_NAME')
POS_DB_USER = _env('ZIVOC_POS_DB_USER')
POS_DB_PASSWORD = _env('ZIVOC_POS_DB_PASSWORD')
POS_ERP_TOKEN = _env('ZIVOC_POS_ERP_TOKEN')
POS_DEFAULT_PASSWORD_HASH = _env('ZIVOC_POS_DEFAULT_PASSWORD_HASH')
