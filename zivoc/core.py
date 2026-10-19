import calendar
import hmac
import re
import secrets
import textwrap
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

import bcrypt
from flask import g, request, session
from markupsafe import Markup, escape

from . import config


class AppError(Exception):
    pass


class Redirect(Exception):
    def __init__(self, location):
        super().__init__(location)
        self.location = location


def tz():
    return ZoneInfo(config.TIMEZONE)


def now():
    return datetime.now(tz()).replace(microsecond=0)


def today():
    return now().strftime('%Y-%m-%d')


def to_dt(value=None):
    if value is None:
        return now().replace(tzinfo=None)
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y-%m', '%Y-%m-%dT%H:%M'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise AppError('Invalid date.')


def php_date(fmt, value=None):
    dt = to_dt(value)
    out = []
    escape_next = False
    for ch in fmt:
        if escape_next:
            out.append(ch)
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
        elif ch == 'd':
            out.append('%02d' % dt.day)
        elif ch == 'j':
            out.append(str(dt.day))
        elif ch == 'D':
            out.append(dt.strftime('%a'))
        elif ch == 'l':
            out.append(dt.strftime('%A'))
        elif ch == 'N':
            out.append(str(dt.isoweekday()))
        elif ch == 'm':
            out.append('%02d' % dt.month)
        elif ch == 'n':
            out.append(str(dt.month))
        elif ch == 'M':
            out.append(dt.strftime('%b'))
        elif ch == 'F':
            out.append(dt.strftime('%B'))
        elif ch == 't':
            out.append(str(calendar.monthrange(dt.year, dt.month)[1]))
        elif ch == 'Y':
            out.append('%04d' % dt.year)
        elif ch == 'y':
            out.append('%02d' % (dt.year % 100))
        elif ch == 'H':
            out.append('%02d' % dt.hour)
        elif ch == 'G':
            out.append(str(dt.hour))
        elif ch == 'h':
            out.append('%02d' % ((dt.hour % 12) or 12))
        elif ch == 'g':
            out.append(str((dt.hour % 12) or 12))
        elif ch == 'i':
            out.append('%02d' % dt.minute)
        elif ch == 's':
            out.append('%02d' % dt.second)
        elif ch == 'a':
            out.append('am' if dt.hour < 12 else 'pm')
        elif ch == 'A':
            out.append('AM' if dt.hour < 12 else 'PM')
        else:
            out.append(ch)
    return ''.join(out)


def add_days(day, days):
    return (to_dt(day) + timedelta(days=days)).strftime('%Y-%m-%d')


def add_months(month_start, months):
    dt = to_dt(month_start)
    index = dt.year * 12 + (dt.month - 1) + months
    return datetime(index // 12, index % 12 + 1, 1)


def php_round(value, digits=0):
    quant = Decimal(1).scaleb(-digits)
    return float(Decimal(repr(float(value))).quantize(quant, rounding=ROUND_HALF_UP))


def number_format(value, decimals=0):
    quant = Decimal(1).scaleb(-decimals)
    amount = Decimal(repr(float(value or 0))).quantize(quant, rounding=ROUND_HALF_UP)
    return f'{amount:,.{decimals}f}'


def money(value):
    return '\u20b9' + number_format(value, 0)


def wf_money(value):
    return '\u20b9' + number_format(value, 2)


NUMERIC_RE = re.compile(r'^\s*[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?\s*$')
INT_RE = re.compile(r'^[+-]?(0|[1-9]\d*)$')


def is_numeric(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float, Decimal)):
        return True
    return isinstance(value, str) and bool(NUMERIC_RE.match(value))


def filter_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if INT_RE.match(text):
            number = int(text)
            if -(2 ** 63) <= number < 2 ** 63:
                return number
    return None


def is_array(value):
    return isinstance(value, dict)


FORM_KEY_RE = re.compile(r'^([^\[]+)((?:\[[^\]]*\])*)$')
FORM_PART_RE = re.compile(r'\[([^\]]*)\]')


def parse_php_form(multidict):
    result = {}
    for name in multidict:
        values = multidict.getlist(name)
        match = FORM_KEY_RE.match(name)
        for value in values:
            if not match:
                result[name] = value
                continue
            base, rest = match.group(1), match.group(2)
            keys = FORM_PART_RE.findall(rest)
            if not keys:
                result[base] = value
                continue
            container = result
            key = base
            for part in keys:
                child = container.get(key)
                if not isinstance(child, dict):
                    child = {}
                    container[key] = child
                container = child
                if part == '':
                    key = len([k for k in container if isinstance(k, int)])
                    while key in container:
                        key += 1
                else:
                    key = part
            container[key] = value
    return result


def post():
    if 'post' not in g:
        g.post = parse_php_form(request.form)
    return g.post


def files():
    return request.files


def hash_equals(a, b):
    return hmac.compare_digest(str(a).encode(), str(b).encode())


def random_hex(nbytes):
    return secrets.token_hex(nbytes)


def hash_password(password):
    raw = password.encode()[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt(10)).decode().replace('$2b$', '$2y$', 1)


def verify_password(password, hashed):
    if not hashed:
        return False
    try:
        normalized = hashed.replace('$2y$', '$2b$', 1).replace('$2x$', '$2b$', 1).replace('$2a$', '$2b$', 1)
        return bcrypt.checkpw(password.encode()[:72], normalized.encode())
    except ValueError:
        return False


def utf8_len(text):
    return len(text.encode('utf-8'))


def php_wordwrap(text, width):
    lines = []
    for paragraph in text.replace('\r', '').split('\n'):
        wrapped = textwrap.wrap(paragraph, width=width, break_long_words=True, break_on_hyphens=False, drop_whitespace=True)
        lines.extend(wrapped if wrapped else [''])
    return lines


def ucwords(text):
    return re.sub(r'(^|\s)(\S)', lambda m: m.group(1) + m.group(2).upper(), text)


def fnum(value):
    text = '%.14G' % value
    if 'E' in text:
        mantissa, exponent = text.split('E')
        if '.' not in mantissa:
            mantissa += '.0'
        text = mantissa + 'E' + exponent[0] + exponent[1:].lstrip('0')
    return text


def html_escape(value):
    return str(escape('' if value is None else value))
