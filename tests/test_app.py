"""Tests de integración con base de datos (SQLite en memoria o TEST_DATABASE_URL de Postgres)."""
import pytest

for _dep in ("flask_sqlalchemy", "flask_login", "flask_limiter", "flask_migrate", "flask_mail"):
    pytest.importorskip(_dep)

from app.extensions import db
from app.models import Product, Sale, StockMovement, Tenant, User

from .helpers import PASSWORD, login, make_product, make_tenant, make_user


def sale(client, items, method='cash'):
    return client.post('/app/pos/api/sale', json={'payment_method': method, 'items': items})


# ── autenticación y permisos ───────────────────────────────
def test_login_redirects_by_role(client, shop):
    assert login(client, shop['employee']).headers['Location'].endswith('/app/pos/terminal')
    client.post('/auth/logout')
    assert login(client, shop['client']).headers['Location'].endswith('/app/turnos/')
    client.post('/auth/logout')
    assert login(client, shop['owner']).headers['Location'].endswith('/app/dashboard/')


def test_wrong_password_and_unknown_email_same_message(client, shop):
    r1 = login(client, shop['owner'], password='mala')
    r2 = client.post('/auth/login', data={'email': 'nadie@x.com', 'password': 'mala'})
    assert r1.status_code == r2.status_code == 401


def test_open_redirect_blocked(client, shop):
    r = client.post('/auth/login?next=https://evil.com', data={'email': shop['owner'].email, 'password': PASSWORD})
    assert 'evil.com' not in r.headers['Location']
    client.post('/auth/logout')
    r = client.post('/auth/login?next=/app/reports/cierre-diario', data={'email': shop['owner'].email, 'password': PASSWORD})
    assert r.headers['Location'].endswith('/app/reports/cierre-diario')


def test_logout_requires_post(client, shop):
    login(client, shop['owner'])
    assert client.get('/auth/logout').status_code == 405
    assert client.post('/auth/logout').status_code == 302


def test_deactivated_user_is_logged_out_without_loop(client, shop):
    login(client, shop['employee'])
    shop['employee'].is_active = False
    db.session.commit()
    r = client.get('/app/pos/terminal')
    assert r.status_code == 302 and '/auth/login' in r.headers['Location']
    assert client.get('/auth/login').status_code == 200   # no redirige en bucle


def test_employee_cannot_see_reports_or_manage(client, shop):
    login(client, shop['employee'])
    for url in ['/app/reports/cierre-diario', '/app/reports/historial-ventas', '/app/dashboard/gestion',
                '/app/dashboard/equipo', '/app/inventory/productos/nuevo', '/app/inventory/movimientos']:
        assert client.get(url).status_code == 403, url
    assert client.post(f"/app/inventory/productos/{shop['product'].id}/eliminar").status_code == 403
    assert client.get('/app/inventory/productos').status_code == 200


def test_employee_does_not_see_cost_prices(client, shop):
    login(client, shop['employee'])
    html = client.get('/app/inventory/productos').get_data(as_text=True)
    assert 'Costo' not in html and 'Margen' not in html


def test_client_only_sees_turnos(client, shop):
    login(client, shop['client'])
    assert 'Módulo en mantenimiento' in client.get('/app/turnos/').get_data(as_text=True)
    assert client.get('/app/pos/terminal').status_code == 403
    assert client.get('/app/inventory/productos').status_code == 403
    assert client.post('/app/pos/api/sale', json={'items': []}).status_code == 403


def test_api_returns_json_401_when_not_logged(client):
    r = client.post('/app/pos/api/sale', json={'items': []})
    assert r.status_code == 401 and r.is_json


# ── códigos de invitación ──────────────────────────────────
def test_join_with_codes_assigns_role(client, app):
    t = make_tenant('Local')
    for code, role in [(t.employee_code, 'employee'), (t.client_code, 'client')]:
        u = User(email=f'{role}@x.com', username='X', is_email_confirmed=True)
        u.set_password(PASSWORD)
        db.session.add(u)
        db.session.commit()
        login(client, u)
        r = client.post('/auth/unirme', data={'code': code.lower().replace('-', ' ')})
        assert r.status_code == 302
        assert db.session.get(User, u.id).role == role
        client.post('/auth/logout')


def test_join_with_bad_code(client, app):
    u = User(email='z@x.com', username='Z', is_email_confirmed=True)
    u.set_password(PASSWORD)
    db.session.add(u)
    db.session.commit()
    login(client, u)
    assert client.post('/auth/unirme', data={'code': 'FX-ZZZZZZ'}).status_code == 400
    assert db.session.get(User, u.id).role is None


def test_employee_plan_limit(client, app):
    t = make_tenant('Chico')
    for i in range(3):
        make_user(t, 'employee', email=f'e{i}@x.com')
    u = User(email='nuevo@x.com', username='N', is_email_confirmed=True)
    u.set_password(PASSWORD)
    db.session.add(u)
    db.session.commit()
    login(client, u)
    assert client.post('/auth/unirme', data={'code': t.employee_code}).status_code == 400


def test_owner_setup_creates_tenant_with_both_codes(client, app):
    u = User(email='dueno@x.com', username='D', is_email_confirmed=True)
    u.set_password(PASSWORD)
    db.session.add(u)
    db.session.commit()
    login(client, u)
    client.post('/auth/setup-owner', data={'business_name': 'Mi Negocio'})
    u = db.session.get(User, u.id)
    assert u.role == 'owner' and u.tenant.employee_code.startswith('FX-') and u.tenant.client_code.startswith('FC-')


# ── ventas y stock ─────────────────────────────────────────
def test_sale_decrements_stock_and_records_movement(client, shop):
    login(client, shop['employee'])
    r = sale(client, [{'product_id': shop['product'].id, 'quantity': 3}])
    assert r.status_code == 200 and r.json['success']
    p = db.session.get(Product, shop['product'].id)
    assert p.stock == 7
    m = StockMovement.query.filter_by(product_id=p.id).one()
    assert m.reason == 'sale' and m.quantity_change == -3 and m.stock_after == 7 and m.sale_id == r.json['sale_id']


def test_sale_uses_server_prices_and_decimal_totals(client, shop):
    p = make_product(shop['tenant'], 'Caramelo', cost='0.10', price='0.30', stock=100)
    login(client, shop['employee'])
    r = client.post('/app/pos/api/sale', json={'items': [{'product_id': p.id, 'quantity': 3, 'price': 0.01}]})
    s = db.session.get(Sale, r.json['sale_id'])
    assert str(s.total_amount) in ('0.90', '0.9') and str(s.total_cost) in ('0.30', '0.3')


def test_sale_rejects_insufficient_stock_and_rolls_back(client, shop):
    p2 = make_product(shop['tenant'], 'Azúcar', stock=1)
    login(client, shop['employee'])
    r = sale(client, [{'product_id': shop['product'].id, 'quantity': 2}, {'product_id': p2.id, 'quantity': 5}])
    assert r.status_code == 400
    assert db.session.get(Product, shop['product'].id).stock == 10    # nada se descontó
    assert Sale.query.count() == 0 and StockMovement.query.count() == 0


@pytest.mark.parametrize('items', [[], None, 'x', [{'product_id': 1, 'quantity': 0}], [{'product_id': 1, 'quantity': -1}],
                                   [{'product_id': 1, 'quantity': 1.5}], [{'product_id': True, 'quantity': 1}], [5]])
def test_sale_rejects_malformed_items(client, shop, items):
    login(client, shop['employee'])
    assert sale(client, items).status_code == 400


def test_sale_merges_duplicate_lines(client, shop):
    login(client, shop['employee'])
    pid = shop['product'].id
    assert sale(client, [{'product_id': pid, 'quantity': 4}, {'product_id': pid, 'quantity': 4}]).status_code == 200
    assert db.session.get(Product, pid).stock == 2
    assert sale(client, [{'product_id': pid, 'quantity': 4}, {'product_id': pid, 'quantity': 4}]).status_code == 400


def test_tenant_isolation_in_sales(client, shop):
    other = make_tenant('Otro')
    foreign = make_product(other, 'Ajeno', stock=5)
    login(client, shop['employee'])
    assert sale(client, [{'product_id': foreign.id, 'quantity': 1}]).status_code == 400
    assert db.session.get(Product, foreign.id).stock == 5
    login_owner = shop['owner']
    client.post('/auth/logout')
    login(client, login_owner)
    assert client.get(f'/app/inventory/productos/{foreign.id}/editar').status_code == 404
    assert client.post(f'/app/inventory/productos/{foreign.id}/stock', data={'kind': 'entry', 'quantity': '5'}).status_code == 404


def test_void_sale_restores_stock_and_excludes_from_metrics(client, shop):
    login(client, shop['employee'])
    sid = sale(client, [{'product_id': shop['product'].id, 'quantity': 4}]).json['sale_id']
    client.post('/auth/logout')
    # El empleado no puede anular
    login(client, shop['employee'])
    assert client.post(f'/app/reports/ventas/{sid}/anular').status_code == 403
    client.post('/auth/logout')
    login(client, shop['owner'])
    assert client.post(f'/app/reports/ventas/{sid}/anular', data={'reason': 'error'}).status_code == 302
    assert db.session.get(Product, shop['product'].id).stock == 10
    assert db.session.get(Sale, sid).is_voided
    reasons = [m.reason for m in StockMovement.query.order_by(StockMovement.id)]
    assert reasons == ['sale', 'sale_void']
    # Anular dos veces no duplica el stock
    client.post(f'/app/reports/ventas/{sid}/anular')
    assert db.session.get(Product, shop['product'].id).stock == 10
    from app.services.metrics import period_totals
    from app.utils.timeutils import local_midnight_utc
    assert period_totals(shop['tenant'].id, local_midnight_utc())['count'] == 0


def test_void_of_other_tenant_sale_404s_gracefully(client, shop):
    other = make_tenant('Otro')
    op = make_product(other, stock=5)
    from app.services.sales import create_sale
    s = create_sale(other.id, None, [{'product_id': op.id, 'quantity': 1}])
    login(client, shop['owner'])
    client.post(f'/app/reports/ventas/{s.id}/anular')
    assert not db.session.get(Sale, s.id).is_voided


# ── movimientos manuales ───────────────────────────────────
def test_manual_movements(client, shop):
    pid = shop['product'].id
    login(client, shop['employee'])
    client.post(f'/app/inventory/productos/{pid}/stock', data={'kind': 'entry', 'quantity': '5'})
    assert db.session.get(Product, pid).stock == 15
    client.post(f'/app/inventory/productos/{pid}/stock', data={'kind': 'loss', 'quantity': '5'})   # sin permiso
    assert db.session.get(Product, pid).stock == 15
    client.post('/auth/logout')
    login(client, shop['owner'])
    client.post(f'/app/inventory/productos/{pid}/stock', data={'kind': 'loss', 'quantity': '3', 'note': 'roto'})
    assert db.session.get(Product, pid).stock == 12
    client.post(f'/app/inventory/productos/{pid}/stock', data={'kind': 'adjust_set', 'quantity': '20'})
    assert db.session.get(Product, pid).stock == 20
    client.post(f'/app/inventory/productos/{pid}/stock', data={'kind': 'loss', 'quantity': '999'})  # más que el stock
    assert db.session.get(Product, pid).stock == 20
    last = StockMovement.query.order_by(StockMovement.id.desc()).first()
    assert last.reason == 'adjustment' and last.quantity_change == 8 and last.stock_after == 20


def test_ledger_always_matches_stock(client, shop):
    login(client, shop['employee'])
    pid = shop['product'].id
    sale(client, [{'product_id': pid, 'quantity': 2}])
    client.post(f'/app/inventory/productos/{pid}/stock', data={'kind': 'entry', 'quantity': '7'})
    total = db.session.query(db.func.sum(StockMovement.quantity_change)).filter_by(product_id=pid).scalar()
    assert total == db.session.get(Product, pid).stock - 10   # 10 era el stock sin movimiento inicial


# ── productos ──────────────────────────────────────────────
def test_product_create_validation_and_initial_stock(client, shop):
    login(client, shop['owner'])
    base = {'name': 'Café', 'cost_price': '1.234,50', 'sale_price': '2000', 'stock': '6', 'low_stock_threshold': '2'}
    assert client.post('/app/inventory/productos/nuevo', data=base).status_code == 302
    p = Product.query.filter_by(name='Café').one()
    assert str(p.cost_price) in ('1234.50', '1234.5') and p.stock == 6
    assert StockMovement.query.filter_by(product_id=p.id, reason='initial').count() == 1
    for bad in [{'cost_price': 'abc'}, {'sale_price': '-5'}, {'name': ''}, {'stock': '-1'}, {'cost_price': 'NaN'}]:
        assert client.post('/app/inventory/productos/nuevo', data={**base, 'name': 'X', **bad}).status_code == 400
    assert Product.query.filter_by(name='X').count() == 0


def test_duplicate_sku_is_friendly_error(client, shop):
    login(client, shop['owner'])
    data = {'name': 'A', 'sku': 'S1', 'cost_price': '1', 'sale_price': '2', 'stock': '0'}
    assert client.post('/app/inventory/productos/nuevo', data=data).status_code == 302
    assert client.post('/app/inventory/productos/nuevo', data={**data, 'name': 'B'}).status_code == 400


def test_deactivate_and_reactivate(client, shop):
    login(client, shop['owner'])
    pid = shop['product'].id
    client.post(f'/app/inventory/productos/{pid}/eliminar')
    assert not db.session.get(Product, pid).is_active
    client.post(f'/app/inventory/productos/{pid}/reactivar')
    assert db.session.get(Product, pid).is_active


def test_search_escapes_wildcards(client, shop):
    make_product(shop['tenant'], 'Oferta 50% off', stock=1)
    login(client, shop['employee'])
    assert [p['name'] for p in client.get('/app/pos/api/products/search?q=%25').json] == ['Oferta 50% off']


# ── métricas / alertas ─────────────────────────────────────
def test_low_stock_alerts_and_badge(client, shop):
    make_product(shop['tenant'], 'Poco', stock=2, low_stock_threshold=3)
    make_product(shop['tenant'], 'Agotado', stock=0)
    login(client, shop['owner'])
    html = client.get('/app/dashboard/gestion').get_data(as_text=True)
    assert 'stock bajo' in html and 'Poco' in html and 'AGOTADO' in html
    from app.services.metrics import low_stock_count
    assert low_stock_count(shop['tenant'].id) == 2


def test_month_metrics_use_decimals(client, shop):
    login(client, shop['employee'])
    sale(client, [{'product_id': shop['product'].id, 'quantity': 2}])
    from app.services.metrics import dashboard_metrics
    m = dashboard_metrics(shop['tenant'].id)
    assert str(m['today']['income']) in ('300.00', '300') and str(m['today']['profit']) in ('100.00', '100')
    assert m['top'][0]['name'] == 'Yerba' and m['top'][0]['qty'] == 2


# ── contraseña / sesiones ──────────────────────────────────
def test_password_change_invalidates_other_sessions(app, shop):
    c1, c2 = app.test_client(), app.test_client()
    login(c1, shop['owner'])
    login(c2, shop['owner'])
    r = c1.post('/app/dashboard/configuracion/actualizar',
                data={'action': 'password', 'current_password': PASSWORD, 'new_password': 'Nueva12345'})
    assert r.status_code == 302
    assert c1.get('/app/dashboard/').status_code == 200            # sigue logueado
    assert c2.get('/app/dashboard/').status_code == 302            # la otra sesión cayó


def test_password_reset_flow(client, shop):
    from app.utils.mailer import SALT_RESET, make_token
    u = shop['owner']
    token = make_token({'id': u.id, 'v': u.auth_version}, SALT_RESET)
    assert client.post(f'/auth/restablecer/{token}', data={'password': 'Otra12345', 'confirm_password': 'Otra12345'}).status_code == 302
    assert db.session.get(User, u.id).check_password('Otra12345')
    # El mismo enlace ya no sirve
    assert client.post(f'/auth/restablecer/{token}', data={'password': 'Tercera123', 'confirm_password': 'Tercera123'}).status_code == 302
    assert db.session.get(User, u.id).check_password('Otra12345')


def test_forgot_password_does_not_reveal_accounts(client, shop):
    a = client.post('/auth/olvide-mi-contrasena', data={'email': shop['owner'].email})
    b = client.post('/auth/olvide-mi-contrasena', data={'email': 'no-existe@x.com'})
    assert a.status_code == b.status_code == 302


def test_deactivating_user_kicks_session(app, shop):
    c = app.test_client()
    login(c, shop['employee'])
    o = app.test_client()
    login(o, shop['owner'])
    o.post(f"/app/dashboard/equipo/{shop['employee'].id}/toggle")
    assert c.get('/app/pos/terminal').status_code == 302


def test_owner_cannot_manage_other_tenant_users(client, shop):
    other = make_tenant('Otro')
    victim = make_user(other, 'employee')
    login(client, shop['owner'])
    assert client.post(f'/app/dashboard/equipo/{victim.id}/toggle').status_code == 404
    assert db.session.get(User, victim.id).is_active


# ── seguridad general ──────────────────────────────────────
def test_csrf_enforced_when_enabled(app, shop):
    app.config['CSRF_ENABLED'] = True
    c = app.test_client()
    # Sin token: se rechaza (con aviso y redirección) y NO se inicia sesión
    r = c.post('/auth/login', data={'email': shop['owner'].email, 'password': PASSWORD})
    assert r.status_code == 302
    assert c.get('/app/dashboard/').status_code == 302
    # El POST de la API sin cabecera tampoco entra
    assert c.post('/app/pos/api/sale', json={'items': []}).status_code in (400, 401)


def test_security_headers_and_healthz(client):
    r = client.get('/healthz')
    assert r.json == {'status': 'ok'}
    assert r.headers['X-Content-Type-Options'] == 'nosniff' and r.headers['X-Frame-Options'] == 'DENY'
    assert client.get('/app/dashboard/').headers.get('Cache-Control') == 'no-store'


def test_error_pages(client):
    r = client.get('/no-existe')
    assert r.status_code == 404 and 'Página no encontrada' in r.get_data(as_text=True)


def test_landing_and_public_pages(client):
    for url in ['/', '/contacto', '/auth/login', '/auth/registro', '/auth/olvide-mi-contrasena']:
        assert client.get(url).status_code == 200, url


def test_production_config_requires_strong_secret(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@localhost/db')
    monkeypatch.setenv('SECRET_KEY', 'corta')
    import config
    import importlib
    importlib.reload(config)
    with pytest.raises(RuntimeError):
        create = __import__('app').create_app
        create('production')
