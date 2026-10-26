import random
import secrets

from flask import Flask, Response, redirect, request
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from . import catalog, config, db, sessions, views
from .core import Redirect


def create_app():
    app = Flask(__name__, static_folder=str(config.BASE_DIR / 'zivoc' / 'assets'), static_url_path='/assets', template_folder='templates')
    app.config['SECRET_KEY'] = secrets.token_hex(32)
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_UPLOAD_BYTES
    app.config['MAX_FORM_MEMORY_SIZE'] = 16 * 1024 * 1024
    app.config['MAX_FORM_PARTS'] = 10000
    if config.TRUST_PROXY:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.session_interface = sessions.FileSessionInterface()
    app.jinja_env.finalize = lambda value: '' if value is None else value
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True
    for directory in (config.SESSION_DIR, config.SELFIE_DIR, config.WORKFLOW_DIR, config.BRAND_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    sessions.purge_expired()
    app.teardown_appcontext(db.close_db)
    views.register(app)

    @app.before_request
    def housekeeping():
        if random.random() < 0.01:
            sessions.purge_expired()

    @app.after_request
    def security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        if request.endpoint == 'static':
            return response
        origin = catalog.product_image_origin()
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        response.headers.setdefault('Cache-Control', 'no-store')
        response.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'self'; img-src 'self' data: blob: %s; style-src 'self'; script-src 'self'; connect-src 'self'; media-src 'self' blob:; "
            "frame-ancestors 'none'; form-action 'self'; base-uri 'self'" % origin,
        )
        return response

    @app.errorhandler(Redirect)
    def handle_redirect(exc):
        return redirect(exc.location, 303)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large(exc):
        return Response('The upload is too large.', 413)

    @app.errorhandler(Exception)
    def handle_error(exc):
        if isinstance(exc, HTTPException):
            return exc
        app.logger.exception('Unhandled error')
        return Response('The request could not be completed. Check the server log or database configuration.', 500)

    return app
