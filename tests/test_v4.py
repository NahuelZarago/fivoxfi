"""v4: actualización masiva de precios, exportaciones, panel de administrador y borrado de cuenta propia."""
import io
from decimal import Decimal

import pytest

for _dep in ("flask_sqlalchemy", "flask_login", "flask_limiter", "flask_migrate", "flask_mail"):
    pytest.importorskip(_dep)

from app.extensions import db
from app.models import PriceChange, Product, Sale, Tenant, User

from .helpers import PASSWORD, login, make_product, make_tenant, make_user

PRICES = '/app/inventory/precios'


def pform(**kw):
    data = {'direction': 'up', 'percent': '10', 'applies_to': 'sale', 'rounding': 'none', 'scope': 'all', 'search': ''}
    data.update(kw)
    return data


def fresh(model, pk):
    db.session.expire_all()
    return db.session.get(model, pk)


def make_admin(email='root@t.com'):
    u = make_user(None, 'x', email=email)
    u.role = None
    u.is_superadmin = True
    db.session.commit()
    return u


# ── precios ────────────────────────────────────────────────
def test_price_preview_does_not_save(client, shop):
    login(client, shop['owner'])
    r = client.post(PRICES + '/vista-previa', data=pform())
    assert r.status_code == 200 and b'165,00' in r.data
    assert fresh(Product, shop['product'].id).sale_price == Decimal('150.00')
    assert PriceChange.query.count() == 0


def test_price_apply_and_revert(client, shop):
    pid = shop['product'].id
    login(client, shop['owner'])
    assert client.post(PRICES + '/aplicar', data=pform()).status_code == 302
    p = fresh(Product, pid)
    assert p.sale_price == Decimal('165.00') and p.cost_price == Decimal('100.00')
    change = PriceChange.query.one()
    assert change.old_sale == Decimal('150.00') and change.new_sale == Decimal('165.00')
    r = client.post(f'{PRICES}/revertir/{change.batch_id}')
    assert r.status_code == 302
    assert fresh(Product, pid).sale_price == Decimal('150.00')
    # no se puede revertir dos veces
    client.post(f'{PRICES}/revertir/{change.batch_id}')
    assert fresh(Product, pid).sale_price == Decimal('150.00')


def test_price_apply_both_with_rounding(client, shop):
    login(client, shop['owner'])
    client.post(PRICES + '/aplicar', data=pform(applies_to='both', rounding='10', percent='8'))
    p = fresh(Product, shop['product'].id)
    assert p.cost_price == Decimal('110.00') and p.sale_price == Decimal('160.00')   # 108 -> 110, 162 -> 160


def test_price_decrease(client, shop):
    login(client, shop['owner'])
    client.post(PRICES + '/aplicar', data=pform(direction='down', percent='20'))
    assert fresh(Product, shop['product'].id).sale_price == Decimal('120.00')


def test_price_scope_search_only_matches(client, shop):
    other = make_product(shop['tenant'], 'Azúcar', cost='50', price='80')
    login(client, shop['owner'])
    client.post(PRICES + '/aplicar', data=pform(scope='search', search='zúcar'))
    assert fresh(Product, other.id).sale_price == Decimal('88.00')
    assert fresh(Product, shop['product'].id).sale_price == Decimal('150.00')


def test_price_search_scope_requires_text(client, shop):
    login(client, shop['owner'])
    r = client.post(PRICES + '/vista-previa', data=pform(scope='search', search=''))
    assert r.status_code == 400


def test_price_update_isolated_between_tenants(client, shop):
    other = make_tenant('Otro')
    foreign = make_product(other, 'Ajeno', price='200')
    login(client, shop['owner'])
    client.post(PRICES + '/aplicar', data=pform())
    assert fresh(Product, foreign.id).sale_price == Decimal('200.00')


def test_cannot_revert_other_tenant_batch(client, shop):
    other = make_tenant('Otro')
    foreign = make_product(other, 'Ajeno', price='200')
    owner2 = make_user(other, 'owner', email='o2@t.com')
    login(client, owner2)
    client.post(PRICES + '/aplicar', data=pform())
    batch = PriceChange.query.filter_by(tenant_id=other.id).first().batch_id
    client.post('/auth/logout')
    login(client, shop['owner'])
    client.post(f'{PRICES}/revertir/{batch}')
    assert fresh(Product, foreign.id).sale_price == Decimal('220.00')


def test_revert_skips_products_changed_afterwards(client, shop):
    p2 = make_product(shop['tenant'], 'Otro prod', price='100')
    login(client, shop['owner'])
    client.post(PRICES + '/aplicar', data=pform())
    p2.sale_price = Decimal('999.00')       # alguien lo cambió a mano después
    db.session.commit()
    batch = PriceChange.query.first().batch_id
    client.post(f'{PRICES}/revertir/{batch}')
    assert fresh(Product, p2.id).sale_price == Decimal('999.00')
    assert fresh(Product, shop['product'].id).sale_price == Decimal('150.00')


@pytest.mark.parametrize('who', ['employee', 'client'])
def test_price_pages_forbidden_for_non_owner(client, shop, who):
    login(client, shop[who])
    assert client.get(PRICES).status_code == 403
    assert client.post(PRICES + '/aplicar', data=pform()).status_code == 403


@pytest.mark.parametrize('bad', ['0', 'abc', '-95', '999', ''])
def test_price_invalid_percent_rejected(client, shop, bad):
    login(client, shop['owner'])
    client.post(PRICES + '/aplicar', data=pform(percent=bad))
    assert fresh(Product, shop['product'].id).sale_price == Decimal('150.00')


def test_revert_rejects_bad_batch_id(client, shop):
    login(client, shop['owner'])
    assert client.post(PRICES + '/revertir/no-es-uuid').status_code == 302
    assert client.get(PRICES).status_code == 200


# ── exportaciones ──────────────────────────────────────────
XLSX = '/app/exportar/descargar/'


def test_export_products_xlsx(client, shop):
    openpyxl = pytest.importorskip('openpyxl')
    login(client, shop['owner'])
    r = client.get(XLSX + 'productos')
    assert r.status_code == 200 and 'spreadsheetml' in r.mimetype
    assert 'attachment' in r.headers['Content-Disposition'] and r.headers['Cache-Control'] == 'no-store'
    ws = openpyxl.load_workbook(io.BytesIO(r.data)).active
    rows = list(ws.iter_rows(values_only=True))
    assert 'Precio de compra' in rows[0] and rows[1][0] == 'Yerba'


def test_export_products_csv(client, shop):
    login(client, shop['owner'])
    r = client.get(XLSX + 'productos?formato=csv')
    assert r.mimetype == 'text/csv' and r.data.startswith(b'\xef\xbb\xbf')
    assert 'Yerba;' in r.data.decode('utf-8-sig')


def test_export_sales_and_movements(client, shop):
    login(client, shop['employee'])
    client.post('/app/pos/api/sale', json={'payment_method': 'cash', 'items': [{'product_id': shop['product'].id, 'quantity': 2}]})
    client.post('/auth/logout')
    login(client, shop['owner'])
    sales = client.get(XLSX + 'ventas?formato=csv').data.decode('utf-8-sig')
    assert 'Yerba;2;150,00;100,00;300,00;100,00' in sales
    moves = client.get(XLSX + 'movimientos?formato=csv').data.decode('utf-8-sig')
    assert 'Venta' in moves


def test_export_excludes_voided_unless_asked(client, shop):
    from app.services.sales import void_sale
    login(client, shop['employee'])
    client.post('/app/pos/api/sale', json={'payment_method': 'cash', 'items': [{'product_id': shop['product'].id, 'quantity': 1}]})
    sale_id = Sale.query.one().id
    void_sale(shop['tenant'].id, sale_id, shop['owner'].id, 'x')
    client.post('/auth/logout')
    login(client, shop['owner'])
    assert 'Yerba' not in client.get(XLSX + 'ventas?formato=csv').data.decode('utf-8-sig')
    assert 'ANULADA' in client.get(XLSX + 'ventas?formato=csv&anuladas=1').data.decode('utf-8-sig')


def test_export_never_leaks_other_tenant(client, shop):
    other = make_tenant('Otro')
    make_product(other, 'SecretoAjeno')
    login(client, shop['owner'])
    for kind in ('productos', 'ventas', 'movimientos'):
        assert b'SecretoAjeno' not in client.get(f'{XLSX}{kind}?formato=csv').data


@pytest.mark.parametrize('who', ['employee', 'client'])
def test_export_forbidden_for_non_owner(client, shop, who):
    login(client, shop[who])
    assert client.get('/app/exportar/').status_code == 403
    assert client.get(XLSX + 'productos').status_code == 403


def test_export_unknown_kind_and_anonymous(client, shop):
    assert client.get(XLSX + 'productos').status_code == 302
    login(client, shop['owner'])
    assert client.get(XLSX + 'usuarios').status_code == 404
    assert client.get('/app/exportar/').status_code == 200


def test_export_product_formula_name_is_neutralized_in_csv(client, shop):
    make_product(shop['tenant'], '=cmd|calc', sku='X1')
    login(client, shop['owner'])
    assert "'=cmd|calc" in client.get(XLSX + 'productos?formato=csv').data.decode('utf-8-sig')


# ── panel de administrador ─────────────────────────────────
def test_admin_hidden_from_everyone_else(client, shop):
    assert client.get('/admin/').status_code == 404                  # anónimo
    login(client, shop['owner'])
    for path in ('/admin/', '/admin/negocios', '/admin/usuarios'):
        assert client.get(path).status_code == 404
    assert client.post(f"/admin/usuarios/{shop['employee'].id}/eliminar", data={'admin_password': PASSWORD}).status_code == 404
    assert db.session.get(User, shop['employee'].id) is not None


def test_admin_pages_render_and_login_redirects(client, shop):
    admin = make_admin()
    r = login(client, admin)
    assert r.headers['Location'].endswith('/admin/')
    for path in ('/admin/', '/admin/negocios', '/admin/negocios?q=kio', '/admin/usuarios', '/admin/usuarios?q=owner'):
        assert client.get(path).status_code == 200, path
    assert b'Kiosco' in client.get('/admin/negocios').data


def test_admin_toggle_and_verify_user(client, shop):
    admin = make_admin()
    emp = shop['employee']
    emp.is_email_confirmed = False
    db.session.commit()
    login(client, admin)
    client.post(f'/admin/usuarios/{emp.id}/verificar')
    assert fresh(User, emp.id).is_email_confirmed
    v = fresh(User, emp.id).auth_version
    client.post(f'/admin/usuarios/{emp.id}/estado')
    u = fresh(User, emp.id)
    assert u.is_active is False and u.auth_version == v + 1


def test_admin_delete_user_needs_admin_password(client, shop):
    admin = make_admin()
    login(client, admin)
    cid = shop['client'].id
    client.post(f'/admin/usuarios/{cid}/eliminar', data={'admin_password': 'mala'})
    assert fresh(User, cid) is not None
    client.post(f'/admin/usuarios/{cid}/eliminar', data={'admin_password': PASSWORD})
    assert fresh(User, cid) is None


def test_admin_cannot_delete_self_other_admin_or_business_owner(client, shop):
    admin, other_admin = make_admin(), make_admin('root2@t.com')
    login(client, admin)
    for target in (admin, other_admin, shop['owner']):
        client.post(f'/admin/usuarios/{target.id}/eliminar', data={'admin_password': PASSWORD})
        assert fresh(User, target.id) is not None


def test_admin_delete_user_keeps_their_sales(client, shop):
    login(client, shop['employee'])
    client.post('/app/pos/api/sale', json={'payment_method': 'cash', 'items': [{'product_id': shop['product'].id, 'quantity': 1}]})
    client.post('/auth/logout')
    admin = make_admin()
    login(client, admin)
    client.post(f"/admin/usuarios/{shop['employee'].id}/eliminar", data={'admin_password': PASSWORD})
    assert Sale.query.count() == 1


def test_admin_tenant_suspend_plan_delete(client, shop):
    admin = make_admin()
    tid = shop['tenant'].id
    login(client, admin)
    client.post(f'/admin/negocios/{tid}/estado')
    assert fresh(Tenant, tid).is_active is False
    client.post(f'/admin/negocios/{tid}/estado')
    client.post(f'/admin/negocios/{tid}/plan', data={'plan': 'pro'})
    assert fresh(Tenant, tid).plan == 'pro'
    client.post(f'/admin/negocios/{tid}/plan', data={'plan': 'gratis-total'})
    assert fresh(Tenant, tid).plan == 'pro'
    # eliminar: nombre exacto + contraseña
    client.post(f'/admin/negocios/{tid}/eliminar', data={'confirm_name': 'mal', 'admin_password': PASSWORD})
    client.post(f'/admin/negocios/{tid}/eliminar', data={'confirm_name': shop['tenant'].name, 'admin_password': 'mala'})
    assert fresh(Tenant, tid) is not None
    client.post(f'/admin/negocios/{tid}/eliminar', data={'confirm_name': shop['tenant'].name, 'admin_password': PASSWORD})
    assert fresh(Tenant, tid) is None
    assert Product.query.filter_by(tenant_id=tid).count() == 0
    assert fresh(User, shop['owner'].id) is not None            # la cuenta del dueño queda


def test_make_admin_cli(app, shop):
    runner = app.test_cli_runner()
    res = runner.invoke(args=['make-admin', shop['owner'].email.upper()])
    assert res.exit_code == 0 and fresh(User, shop['owner'].id).is_superadmin
    res = runner.invoke(args=['remove-admin', shop['owner'].email])
    assert res.exit_code == 0 and not fresh(User, shop['owner'].id).is_superadmin
    assert runner.invoke(args=['make-admin', 'nadie@x.com']).exit_code != 0


def test_registration_never_grants_admin(client):
    client.post('/auth/registro', data={'username': 'Eve', 'email': 'eve@t.com', 'password': 'Clave1234!x',
                                        'confirm_password': 'Clave1234!x', 'is_superadmin': '1'})
    u = User.query.filter_by(email='eve@t.com').first()
    assert u is not None and u.is_superadmin is False


# ── borrar mi cuenta ───────────────────────────────────────
ACC = '/app/dashboard/configuracion/eliminar-cuenta'


def test_employee_can_delete_own_account(client, shop):
    emp_id, emp_email = shop['employee'].id, shop['employee'].email   # el objeto deja de ser válido al borrarse
    login(client, shop['employee'])
    client.post(ACC, data={'password': 'mala', 'confirm_email': emp_email})
    client.post(ACC, data={'password': PASSWORD, 'confirm_email': 'otro@x.com'})
    assert fresh(User, emp_id) is not None
    r = client.post(ACC, data={'password': PASSWORD, 'confirm_email': emp_email})
    assert r.status_code == 302
    db.session.expire_all()
    assert db.session.get(User, emp_id) is None
    assert client.get('/app/dashboard/').status_code == 302      # sesión cerrada


def test_owner_cannot_delete_account_while_business_exists(client, shop):
    login(client, shop['owner'])
    client.post(ACC, data={'password': PASSWORD, 'confirm_email': shop['owner'].email})
    assert fresh(User, shop['owner'].id) is not None


def test_settings_shows_delete_account_only_to_non_owner(client, shop):
    login(client, shop['employee'])
    assert b'Eliminar mi cuenta' in client.get('/app/dashboard/configuracion').data
    client.post('/auth/logout')
    login(client, shop['owner'])
    assert b'Eliminar mi cuenta' not in client.get('/app/dashboard/configuracion').data