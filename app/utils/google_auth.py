"""
Inicio de sesión con Google (OAuth 2.0 / OpenID Connect, flujo "authorization code" con PKCE).

Sin dependencias nuevas: usa urllib. El código se canjea directamente con Google por HTTPS y los datos
del usuario se piden con el access_token, así que no hace falta validar firmas de JWT.
"""
import base64
import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request

AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
USERINFO_URL = 'https://openidconnect.googleapis.com/v1/userinfo'
TIMEOUT = 10


class GoogleAuthError(Exception):
    """Mensaje seguro para mostrarle a la persona."""


def is_configured(config):
    return bool(config.get('GOOGLE_CLIENT_ID') and config.get('GOOGLE_CLIENT_SECRET'))


def new_state():
    return secrets.token_urlsafe(32)


def pkce_pair():
    """(verifier, challenge) según RFC 7636 (método S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


def build_auth_url(client_id, redirect_uri, state, code_challenge):
    params = {
        'response_type': 'code', 'client_id': client_id, 'redirect_uri': redirect_uri,
        'scope': 'openid email profile', 'state': state, 'prompt': 'select_account',
        'code_challenge': code_challenge, 'code_challenge_method': 'S256',
    }
    return f'{AUTH_URL}?{urllib.parse.urlencode(params)}'


def _request(req):
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:      # noqa: S310 - URLs fijas de Google (https)
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError:
        raise GoogleAuthError('Google rechazó el inicio de sesión. Probá de nuevo.')
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        raise GoogleAuthError('No pudimos conectar con Google. Probá de nuevo en un momento.')


def exchange_code(client_id, client_secret, code, redirect_uri, code_verifier):
    """Canjea el código por un access_token."""
    body = urllib.parse.urlencode({
        'code': code, 'client_id': client_id, 'client_secret': client_secret,
        'redirect_uri': redirect_uri, 'grant_type': 'authorization_code', 'code_verifier': code_verifier,
    }).encode('ascii')
    data = _request(urllib.request.Request(TOKEN_URL, data=body, method='POST',
                                           headers={'Content-Type': 'application/x-www-form-urlencoded'}))
    token = data.get('access_token') if isinstance(data, dict) else None
    if not isinstance(token, str) or not token:
        raise GoogleAuthError('Google no devolvió una sesión válida.')
    return token


def fetch_userinfo(access_token):
    data = _request(urllib.request.Request(USERINFO_URL, headers={'Authorization': f'Bearer {access_token}'}))
    if not isinstance(data, dict):
        raise GoogleAuthError('Google devolvió datos inválidos.')
    return data


def parse_profile(info):
    """Valida lo que devuelve Google. Devuelve {'sub', 'email', 'name'}."""
    sub, email = info.get('sub'), info.get('email')
    if not isinstance(sub, str) or not sub or len(sub) > 64 or not isinstance(email, str) or '@' not in email:
        raise GoogleAuthError('Google no nos dio tu email.')
    if info.get('email_verified') not in (True, 'true'):
        raise GoogleAuthError('Tu cuenta de Google no tiene el email verificado.')
    email = email.strip().lower()
    if len(email) > 120:
        raise GoogleAuthError('Tu email es demasiado largo.')
    name = info.get('name') if isinstance(info.get('name'), str) else ''
    name = ' '.join(name.split())[:80] or email.split('@')[0][:80]
    return {'sub': sub, 'email': email, 'name': name}
