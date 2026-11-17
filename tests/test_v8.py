"""v8: inicio de sesión con Google (las llamadas a Google se simulan)."""
import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest

for _dep in ("flask_sqlalchemy", "flask_login", "flask_limiter", "flask_migrate", "flask_mail"):
    pytest.importorskip(_dep)

from app.extensions import db
from app.models import User
from app.utils import google_auth

from .helpers import PASSWORD, make_user

INFO = {'sub': 'g-123', 'email': 'nuevo@gmail.com', 'email_verified': True, 'name': 'Nuevo Usuario'}


@pytest.fixture()
def google(app, monkeypatch):
    """Configura Google y simula el canje del código y el pedido de datos."""
    app.config.update(GOOGLE_CLIENT_ID='cid', GOOGLE_CLIENT_SECRET='secret')
    state = {'info': dict(INFO), 'calls': [], 'error': None}

    def fake_exchange(client_id, client_secret, code, redirect_uri, verifier):
        state['calls'].append({'code': code, 'verifier': verifier, 'redirect': redirect_uri})
        if state['error']:
            raise google_auth.GoogleAuthError(state['error'])
        return 'access-token'

    monkeypatch.setattr(google_auth, 'exchange_code', fake_exchange)
    monkeypatch.setattr(google_auth, 'fetch_userinfo', lambda token: state['info'])
    return state


def start(client):
    r = client.get('/auth/google')
    assert r.status_code == 302
    return r.headers['Location'], parse_qs(urlparse(r.headers['Location']).query)


def finish(client, state_value, code='the-code', **extra):
    return client.get('/auth/google/callback', query_string={'state': state_value, 'code': code, **extra})


def sign_in(client):
    _, q = start(client)
    return finish(client, q['state'][0])


def logged_in(client):
    return client.get('/auth/elegir-rol').status_code == 200


# ── inicio ─────────────────────────────────────────────────
def test_start_redirects_to_google_with_pkce(client, google):
    url, q = start(client)
    assert url.startswith('https://accounts.google.com/') and q['client_id'] == ['cid']
    assert q['code_challenge_method'] == ['S256'] and q['state'] and q['redirect_uri'][0].endswith('/auth/google/callback')
    finish(client, q['state'][0])
    verifier = google['calls'][0]['verifier']
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    assert q['code_challenge'] == [expected]                      # el verifier guardado corresponde al challenge enviado


def test_start_without_credentials_goes_back_to_login(app, client):
    r = client.get('/auth/google')
    assert r.status_code == 302 and r.headers['Location'].endswith('/auth/login')


def test_button_only_shows_when_configured(app, client):
    assert b'Continuar con Google' not in client.get('/auth/login').data
    app.config.update(GOOGLE_CLIENT_ID='cid', GOOGLE_CLIENT_SECRET='secret')
    assert b'Continuar con Google' in client.get('/auth/login').data
    assert b'Registrarme con Google' in client.get('/auth/registro').data


# ── cuenta nueva ───────────────────────────────────────────
def test_new_google_user_is_created_and_logged_in(client, google):
    r = sign_in(client)
    assert r.status_code == 302 and r.headers['Location'].endswith('/auth/elegir-rol')
    u = User.query.filter_by(email='nuevo@gmail.com').one()
    assert u.google_sub == 'g-123' and u.username == 'Nuevo Usuario'
    assert u.is_email_confirmed and u.is_active and u.role is None and u.is_superadmin is False
    assert not u.check_password('') and not u.check_password('Clave1234')      # sin contraseña usable
    assert logged_in(client)


# ── cuenta existente ───────────────────────────────────────
def test_existing_verified_user_is_linked_and_keeps_password(client, google, shop):
    owner = shop['owner']
    google['info'] = {**INFO, 'email': owner.email}
    r = sign_in(client)
    assert r.headers['Location'].endswith('/app/dashboard/')           # llega a su pantalla de dueño
    db.session.expire_all()
    u = db.session.get(User, owner.id)
    assert u.google_sub == 'g-123' and u.check_password(PASSWORD)
    assert User.query.count() == 3                                      # no se creó un duplicado


def test_second_login_finds_user_by_google_id_even_if_email_changed(client, google):
    sign_in(client)
    client.post('/auth/logout')
    google['info'] = {**INFO, 'email': 'otro-email@gmail.com'}
    sign_in(client)
    assert User.query.count() == 1 and User.query.one().email == 'nuevo@gmail.com'


def test_unverified_account_is_taken_over_safely(client, google):
    """Alguien se registró antes con el email de otra persona: al entrar ella con Google, la contraseña vieja deja de servir."""
    squatter = make_user(None, 'x', email='nuevo@gmail.com')
    squatter.role, squatter.is_email_confirmed = None, False
    db.session.commit()
    version = squatter.auth_version
    sign_in(client)
    db.session.expire_all()
    u = User.query.filter_by(email='nuevo@gmail.com').one()
    assert u.is_email_confirmed and not u.check_password(PASSWORD) and u.auth_version == version + 1
    assert logged_in(client)


def test_inactive_user_is_refused(client, google, shop):
    emp = shop['employee']
    emp.is_active = False
    db.session.commit()
    google['info'] = {**INFO, 'email': emp.email}
    r = sign_in(client)
    assert r.headers['Location'].endswith('/auth/login') and not logged_in(client)


def test_email_already_linked_to_another_google_account_is_refused(client, google, shop):
    emp = shop['employee']
    emp.google_sub = 'otra-persona'
    db.session.commit()
    google['info'] = {**INFO, 'email': emp.email}
    r = sign_in(client)
    assert r.headers['Location'].endswith('/auth/login') and not logged_in(client)
    assert db.session.get(User, emp.id).google_sub == 'otra-persona'


# ── rechazos ───────────────────────────────────────────────
def test_unverified_google_email_is_refused(client, google):
    google['info'] = {**INFO, 'email_verified': False}
    r = sign_in(client)
    assert r.headers['Location'].endswith('/auth/login') and User.query.count() == 0 and not logged_in(client)


def test_wrong_state_is_refused(client, google):
    start(client)
    r = finish(client, 'estado-falso')
    assert r.headers['Location'].endswith('/auth/login') and not google['calls'] and User.query.count() == 0


def test_callback_without_starting_is_refused(client, google):
    r = finish(client, 'cualquiera')
    assert r.headers['Location'].endswith('/auth/login') and not google['calls']


def test_state_is_single_use(client, google):
    _, q = start(client)
    finish(client, q['state'][0])
    client.post('/auth/logout')
    r = finish(client, q['state'][0])                                  # repetir la misma respuesta
    assert r.headers['Location'].endswith('/auth/login') and len(google['calls']) == 1 and not logged_in(client)


def test_user_cancelled_at_google(client, google):
    _, q = start(client)
    r = client.get('/auth/google/callback', query_string={'error': 'access_denied', 'state': q['state'][0]})
    assert r.headers['Location'].endswith('/auth/login') and not google['calls']


def test_google_failure_shows_error_and_creates_nothing(client, google):
    google['error'] = 'No pudimos conectar con Google. Probá de nuevo en un momento.'
    _, q = start(client)
    r = finish(client, q['state'][0])
    assert r.headers['Location'].endswith('/auth/login') and User.query.count() == 0
    assert 'No pudimos conectar con Google'.encode() in client.get('/auth/login').data


def test_signed_in_user_skips_google_flow(client, google, shop):
    from .helpers import login
    login(client, shop['owner'])
    r = client.get('/auth/google')
    assert r.status_code == 302 and 'accounts.google.com' not in r.headers['Location']


def test_settings_explains_password_for_google_users(client, google, shop):
    emp = shop['employee']
    emp.google_sub = 'g-9'
    db.session.commit()
    from .helpers import login
    login(client, emp)
    assert 'Entrás con Google'.encode() in client.get('/app/dashboard/configuracion').data
