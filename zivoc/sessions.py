import json
import os
import re
import secrets
import time

from flask.sessions import SessionInterface, SessionMixin
from werkzeug.datastructures import CallbackDict

from . import config

COOKIE_NAME = 'ZSESSID'
SID_RE = re.compile(r'^[0-9a-f]{48}$')


class FileSession(CallbackDict, SessionMixin):
    def __init__(self, data=None, sid=None, is_new=True):
        def on_update(self):
            self.modified = True

        super().__init__(data or {}, on_update)
        self.sid = sid
        self.is_new = is_new
        self.modified = False
        self.old_sid = None
        self.destroyed = False

    def regenerate(self):
        self.old_sid = self.sid
        self.sid = secrets.token_hex(24)
        self.modified = True

    def destroy(self):
        self.clear()
        self.destroyed = True
        self.modified = True


class FileSessionInterface(SessionInterface):
    def _path(self, sid):
        return config.SESSION_DIR / sid

    def open_session(self, app, request):
        sid = request.cookies.get(COOKIE_NAME, '')
        if SID_RE.match(sid):
            path = self._path(sid)
            try:
                if path.is_file() and time.time() - path.stat().st_mtime < config.SESSION_LIFETIME_SECONDS:
                    with open(path, 'r', encoding='utf-8') as handle:
                        data = json.load(handle)
                    os.utime(path, None)
                    return FileSession(data, sid=sid, is_new=False)
            except (OSError, ValueError):
                pass
        return FileSession(sid=secrets.token_hex(24), is_new=True)

    def save_session(self, app, session, response):
        secure = self._secure(app)
        if session.destroyed:
            for sid in (session.sid, session.old_sid):
                if sid:
                    try:
                        os.unlink(self._path(sid))
                    except OSError:
                        pass
            response.delete_cookie(COOKIE_NAME, path='/')
            return
        if not session and session.is_new:
            return
        if session.modified or session.is_new:
            config.SESSION_DIR.mkdir(parents=True, exist_ok=True)
            path = self._path(session.sid)
            temporary = path.with_name(path.name + '.tmp')
            with open(temporary, 'w', encoding='utf-8') as handle:
                json.dump(dict(session), handle, default=str)
            os.replace(temporary, path)
            if session.old_sid:
                try:
                    os.unlink(self._path(session.old_sid))
                except OSError:
                    pass
        if session.modified or session.is_new:
            response.set_cookie(
                COOKIE_NAME,
                session.sid,
                httponly=True,
                secure=secure,
                samesite='Lax',
                path='/',
            )
        response.vary.add('Cookie')

    def _secure(self, app):
        from flask import request
        if config.COOKIE_SECURE in ('1', 'true', 'yes', 'on'):
            return True
        if config.COOKIE_SECURE in ('0', 'false', 'no', 'off'):
            return False
        forwarded = request.headers.get('X-Forwarded-Proto', '')
        return request.is_secure or forwarded.lower() == 'https'


def purge_expired():
    cutoff = time.time() - config.SESSION_LIFETIME_SECONDS
    try:
        for entry in config.SESSION_DIR.iterdir():
            try:
                if entry.is_file() and entry.stat().st_mtime < cutoff:
                    entry.unlink()
            except OSError:
                continue
    except OSError:
        pass
