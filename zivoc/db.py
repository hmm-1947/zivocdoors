import pymysql
from pymysql import converters
from pymysql.constants import FIELD_TYPE
from pymysql.cursors import DictCursor
from flask import g, has_app_context

from . import config

_conv = converters.conversions.copy()
for _type in (FIELD_TYPE.DATE, FIELD_TYPE.DATETIME, FIELD_TYPE.TIMESTAMP, FIELD_TYPE.TIME, FIELD_TYPE.NEWDATE):
    _conv[_type] = lambda value: value

MySQLError = pymysql.MySQLError


def tz_offset():
    from .core import now
    offset = now().strftime('%z')
    return offset[:3] + ':' + offset[3:]


def connect(host=None, port=None, user=None, password=None, database=None):
    connection = pymysql.connect(
        host=host if host is not None else config.DB_HOST,
        port=port if port is not None else config.DB_PORT,
        user=user if user is not None else config.DB_USER,
        password=password if password is not None else config.DB_PASSWORD,
        database=database if database is not None else config.DB_NAME,
        charset='utf8mb4',
        autocommit=True,
        cursorclass=DictCursor,
        conv=_conv,
        connect_timeout=10,
    )
    with connection.cursor() as cursor:
        cursor.execute("SET time_zone = '%s'" % tz_offset())
    return connection


def conn():
    if 'db' not in g:
        g.db = connect()
    return g.db


def close_db(exception=None):
    connection = g.pop('db', None)
    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass


def q(sql, params=None):
    cursor = conn().cursor()
    cursor.execute(sql, tuple(params) if params else None)
    return cursor


def rows(sql, params=None):
    cursor = q(sql, params)
    try:
        return list(cursor.fetchall())
    finally:
        cursor.close()


def one(sql, params=None):
    result = rows(sql, params)
    return result[0] if result else None


def insert_id():
    return conn().insert_id()


def begin():
    conn().begin()


def commit():
    conn().commit()


def rollback():
    try:
        conn().rollback()
    except Exception:
        pass
