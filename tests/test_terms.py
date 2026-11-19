"""v9: Términos y Condiciones: páginas públicas, casilla obligatoria en el registro y registro de la aceptación."""
import pytest

for _dep in ("flask_sqlalchemy", "flask_login", "flask_limiter", "flask_migrate", "flask_mail"):
    pytest.importorskip(_dep)

from app.models import User
from app.utils.legal import TERMS_VERSION

DATA = {'username': 'Ana', 'email': 'ana@x.com', 'password': 'Clave1234', 'confirm_password': 'Clave1234'}


def test_terms_and_privacy_pages_are_public(client):
    r = client.get('/terminos')
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and 'Términos y Condiciones de Uso' in html and 'no son comprobantes fiscales' in html
    r = client.get('/privacidad')
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and 'Ley 25.326' in html and 'Política de Privacidad' in html


def test_register_form_shows_checkbox_with_links(client):
    html = client.get('/auth/registro').get_data(as_text=True)
    assert 'name="accept_terms"' in html and 'aceptar los' in html and '/terminos' in html and '/privacidad' in html


def test_register_requires_terms(client):
    r = client.post('/auth/registro', data=DATA)
    assert r.status_code == 400 and 'Tenés que aceptar los Términos y Condiciones' in r.get_data(as_text=True)
    assert User.query.count() == 0


def test_register_with_terms_stores_acceptance(client):
    r = client.post('/auth/registro', data={**DATA, 'accept_terms': '1'})
    assert r.status_code == 302
    user = User.query.filter_by(email='ana@x.com').one()
    assert user.terms_accepted_at is not None and user.terms_version == TERMS_VERSION


def test_failed_register_keeps_checkbox_checked(client):
    r = client.post('/auth/registro', data={**DATA, 'email': 'malo', 'accept_terms': '1'})
    html = r.get_data(as_text=True)
    assert r.status_code == 400 and 'checked' in html


def test_google_signup_records_acceptance(app):
    from app.services.google_oauth import login_or_create
    user, created = login_or_create({'sub': 'g-9', 'email': 'g@gmail.com', 'name': 'G', 'email_verified': True})
    assert created and user.terms_accepted_at is not None and user.terms_version == TERMS_VERSION
