"""
Protección CSRF para formularios y fetch().

Sin esto, cualquier sitio web podría hacer que el navegador de un usuario
logueado envíe un POST a Fivox (por ejemplo, anular ventas o dar de baja a un
empleado) usando su cookie de sesión.

Funcionamiento:
  - Cada sesión tiene un token aleatorio.
  - Los formularios lo incluyen en un campo oculto: {{ csrf_input() }}
  - Los fetch() lo mandan en el header X-CSRFToken (leído de <meta name="csrf-token">).
  - Todo POST/PUT/PATCH/DELETE sin token válido se rechaza con 400.

Webhooks de terceros (ej. Mercado Pago) que no pueden mandar el token se marcan
con @csrf_exempt y DEBEN validar su propia firma.
"""
import hmac
import secrets
from functools import wraps

from flask import abort, current_app, request, session
from markupsafe import Markup, escape

SESSION_KEY = '_csrf_token'
FORM_FIELD = 'csrf_token'
HEADER_NAME = 'X-CSRFToken'
SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS', 'TRACE'})


def generate_csrf_token():
    token = session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[SESSION_KEY] = token
    return token


def rotate_csrf_token():
    """Genera un token nuevo. Se llama al iniciar y cerrar sesión."""
    session.pop(SESSION_KEY, None)
    return generate_csrf_token()


def csrf_input():
    """HTML del campo oculto para los formularios."""
    return Markup('<input type="hidden" name="%s" value="%s">') % (FORM_FIELD, escape(generate_csrf_token()))


def csrf_exempt(view):
    """Excluye una vista de la verificación CSRF (solo webhooks con firma propia)."""
    view._csrf_exempt = True
    return view


def _is_valid():
    expected = session.get(SESSION_KEY)
    supplied = request.headers.get(HEADER_NAME) or request.form.get(FORM_FIELD)
    if not expected or not supplied:
        return False
    return hmac.compare_digest(str(expected), str(supplied))


def init_csrf(app):
    @app.before_request
    def _protect_against_csrf():
        if not app.config.get('CSRF_ENABLED', True):
            return None
        if request.method in SAFE_METHODS:
            return None
        view = current_app.view_functions.get(request.endpoint)
        if view is not None and getattr(view, '_csrf_exempt', False):
            return None
        if not _is_valid():
            abort(400, description='csrf')
        return None

    app.jinja_env.globals['csrf_token'] = generate_csrf_token
    app.jinja_env.globals['csrf_input'] = csrf_input
