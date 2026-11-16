"""
Application factory de Fivox.

Los imports de Flask-SQLAlchemy, Flask-Login, etc. están DENTRO de create_app()
a propósito: así los módulos puros (`app.utils.*`) se pueden importar y probar
sin cargar toda la aplicación.
"""
import logging
import os

_MIN_SECRET_LENGTH = 32


def create_app(config_name=None):
    from flask import Flask
    from werkzeug.middleware.proxy_fix import ProxyFix

    from config import config as config_map

    from .errors import register_error_handlers
    from .extensions import db, limiter, login_manager, mail, migrate
    from .utils.csrf import init_csrf
    from .utils.templating import register_context, register_filters

    config_name = config_name or os.environ.get('APP_ENV') or os.environ.get('FLASK_ENV') or 'default'
    if config_name not in config_map:
        raise RuntimeError(f"Entorno inválido: '{config_name}'. Opciones: {', '.join(config_map)}")

    app = Flask(__name__)
    app.config.from_object(config_map[config_name])
    _validate_config(app, config_name)
    _configure_logging(app)

    # Detrás de un proxy (Nginx, Render...) hay que confiar en sus headers para
    # conocer la IP real (rate limiting) y el esquema https (cookies seguras).
    # Solo se activa si TRUST_PROXY=true: si no, cualquiera podría falsificar su IP.
    if app.config['TRUST_PROXY']:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    from . import models  # noqa: F401  Registra los modelos para Alembic

    init_csrf(app)
    register_filters(app)
    register_context(app)
    register_error_handlers(app)
    _register_blueprints(app)
    _register_health_check(app)
    _register_security_headers(app)
    return app


def _validate_config(app, config_name):
    """Falla al arrancar en vez de arrancar inseguro."""
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError(
            'Falta SECRET_KEY. Generá una con: '
            'python -c "import secrets; print(secrets.token_urlsafe(64))"')
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        raise RuntimeError('Falta la URL de la base de datos (DATABASE_URL, o DEV_DATABASE_URL en desarrollo).')
    if config_name == 'production':
        if len(app.config['SECRET_KEY']) < _MIN_SECRET_LENGTH:
            raise RuntimeError(f'SECRET_KEY debe tener al menos {_MIN_SECRET_LENGTH} caracteres en producción.')
        if app.config['RATELIMIT_STORAGE_URI'].startswith('memory://'):
            app.logger.warning(
                'RATELIMIT_STORAGE_URI usa memoria: con varios workers de Gunicorn cada uno cuenta por separado. '
                'Usá Redis (redis://...) en producción.')


def _configure_logging(app):
    if not app.debug and not app.testing:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s [%(name)s] %(message)s')


def _register_blueprints(app):
    from .blueprints.appointments import appointments_bp
    from .blueprints.auth import auth_bp
    from .blueprints.dashboard import dashboard_bp
    from .blueprints.inventory import inventory_bp
    from .blueprints.pos import pos_bp
    from .blueprints.public import public_bp
    from .blueprints.reports import reports_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/app/dashboard')
    app.register_blueprint(inventory_bp, url_prefix='/app/inventory')
    app.register_blueprint(pos_bp, url_prefix='/app/pos')
    app.register_blueprint(reports_bp, url_prefix='/app/reports')
    app.register_blueprint(appointments_bp, url_prefix='/app/turnos')


def _register_health_check(app):
    from sqlalchemy import text

    from .extensions import db

    @app.get('/healthz')
    def healthz():
        # Para Docker / Render / monitoreo: verifica también la conexión a la base.
        db.session.execute(text('SELECT 1'))
        return {'status': 'ok'}


def _register_security_headers(app):
    from flask import request

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'microphone=(), geolocation=()')
        if app.config.get('SESSION_COOKIE_SECURE'):
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        if request.path.startswith(('/app', '/auth')):
            # Páginas con datos del negocio: que el botón "Atrás" no las muestre
            # desde la caché después de cerrar sesión.
            response.headers['Cache-Control'] = 'no-store'
        return response
