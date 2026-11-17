import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


def normalize_database_url(url):
    """
    Heroku/Render/Railway entregan 'postgres://...' y SQLAlchemy 2.x solo
    entiende 'postgresql://...'. Sin esto, el deploy falla al conectar.
    """
    if url and url.startswith('postgres://'):
        return 'postgresql://' + url[len('postgres://'):]
    return url


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,   # Descarta conexiones muertas antes de usarlas
        'pool_recycle': 1800,
    }
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024  # 1 MB: ningún formulario necesita más

    # ── Sesión y cookies ───────────────────────────────────
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)

    # ── Seguridad ──────────────────────────────────────────
    CSRF_ENABLED = True
    TRUST_PROXY = _env_bool('TRUST_PROXY', False)  # True solo detrás de Nginx/Render/etc.
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_HEADERS_ENABLED = True

    # ── Email ──────────────────────────────────────────────
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME')

    # ── Inicio de sesión con Google (opcional: sin estas dos variables el botón no aparece) ──
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or None
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') or None
    GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI') or None   # si vacío: /auth/google/callback del sitio

    # ── Negocio ────────────────────────────────────────────
    # Límite de empleados activos por plan (None = sin límite).
    PLAN_EMPLOYEE_LIMITS = {'basic': 3, 'pro': None}
    SUPPORT_WHATSAPP = os.environ.get('SUPPORT_WHATSAPP', '5491100000000')  # Reemplazar por el real
    # True cuando se compila Tailwind (ver README) y se sirve /static/css/app.css
    USE_COMPILED_CSS = _env_bool('USE_COMPILED_CSS', False)


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-only-insecure-key-change-me'
    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.environ.get('DEV_DATABASE_URL') or os.environ.get('DATABASE_URL'))


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get('DATABASE_URL'))
    SESSION_COOKIE_SECURE = True    # Solo por HTTPS
    REMEMBER_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = 'test-secret-key-not-for-production-0123456789'
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'sqlite:///:memory:')
    SQLALCHEMY_ENGINE_OPTIONS = {}
    CSRF_ENABLED = False             # Un test dedicado la activa
    RATELIMIT_ENABLED = False
    # Los tests nunca usan las credenciales reales de tu .env (cada test que las necesita las pone a mano).
    GOOGLE_CLIENT_ID = None
    GOOGLE_CLIENT_SECRET = None
    GOOGLE_REDIRECT_URI = None
    MAIL_USERNAME = 'tests@fivox.local'  # Con TESTING, Flask-Mail no envía nada
    MAIL_DEFAULT_SENDER = 'tests@fivox.local'
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}