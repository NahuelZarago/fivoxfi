"""v6: categorías y proveedores."""
from decimal import Decimal

import pytest

for _dep in ("flask_sqlalchemy", "flask_login", "flask_limiter", "flask_migrate", "flask_mail"):
    pytest.importorskip(_dep)

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Category, Product, Supplier
from app.services.tenants import delete_tenant

from .helpers import PASSWORD, login, make_product, make_tenant, make_user

CAT = '/app/catalogo/categorias'
SUP = '/app/catalogo/proveedores'
PRICES = '/app/inventory/precios'


def fresh(model, pk):
    db.session.expire_all()
    return db.session.get(model, pk)


def make_cat(tenant, name='Bebidas'):
    c = Category(tenant_id=tenant.id, name=name)
    db.session.add(c)
    db.session.commit()
    return c


def make_sup(tenant, name='Coca'):
    s = Supplier(tenant_id=tenant.id, name=name)
    db.session.add(s)
    db.session.commit()
    return s


def new_product(client, **kw):
    data = {'name': 'Gaseosa', 'cost_price': '100', 'sale_price': '150', 'stock': '5', 'low_stock_threshold': '2'}
    data.update(kw)
    return client.post('/app/inventory/productos/nuevo', data=data)


# ── categorías ─────────────────────────────────────────────
def test_category_crud(client, shop):
    login(client, shop['owner'])
    client.post(CAT + '/crear', data={'name': 'Bebidas'})
    cat = Category.query.one()
    assert cat.name == 'Bebidas' and cat.tenant_id == shop['tenant'].id
    client.post(CAT + '/crear', data={'name': 'bebidas'})                      # duplicada sin importar mayúsculas
    assert Category.query.count() == 1
    client.post(f'{CAT}/{cat.id}/renombrar', data={'name': 'Almacén'})
    assert fresh(Category, cat.id).name == 'Almacén'
    assert client.get(CAT).status_code == 200
    client.post(f'{CAT}/{cat.id}/eliminar')
    assert Category.query.count() == 0


def test_same_category_name_allowed_in_other_tenant(shop):
    other = make_tenant('Otro')
    make_cat(shop['tenant'], 'Bebidas')
    make_cat(other, 'Bebidas')
    assert Category.query.count() == 2


def test_db_unique_category_name_per_tenant(shop):
    make_cat(shop['tenant'], 'X')
    db.session.add(Category(tenant_id=shop['tenant'].id, name='X'))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_deleting_category_keeps_products(client, shop):
    cat = make_cat(shop['tenant'])
    p = shop['product']
    p.category_id = cat.id
    db.session.commit()
    login(client, shop['owner'])
    client.post(f'{CAT}/{cat.id}/eliminar')
    p = fresh(Product, p.id)
    assert p is not None and p.category_id is None


def test_cannot_touch_other_tenant_category(client, shop):
    other = make_tenant('Otro')
    foreign = make_cat(other, 'Ajena')
    login(client, shop['owner'])
    client.post(f'{CAT}/{foreign.id}/renombrar', data={'name': 'Hackeada'})
    client.post(f'{CAT}/{foreign.id}/eliminar')
    assert fresh(Category, foreign.id).name == 'Ajena'


@pytest.mark.parametrize('who', ['employee', 'client'])
def test_catalog_forbidden_for_non_owner(client, shop, who):
    login(client, shop[who])
    for path in (CAT, SUP, SUP + '/nuevo'):
        assert client.get(path).status_code == 403
    assert client.post(CAT + '/crear', data={'name': 'X'}).status_code == 403
    assert Category.query.count() == 0


# ── productos con categoría / proveedor ────────────────────
def test_product_gets_category_and_supplier(client, shop):
    cat, sup = make_cat(shop['tenant']), make_sup(shop['tenant'])
    login(client, shop['owner'])
    new_product(client, category_id=str(cat.id), supplier_id=str(sup.id))
    p = Product.query.filter_by(name='Gaseosa').one()
    assert p.category_id == cat.id and p.supplier_id == sup.id
    assert p.category.name == 'Bebidas' and p.supplier.name == 'Coca'
    client.post(f'/app/inventory/productos/{p.id}/editar', data={
        'name': 'Gaseosa', 'cost_price': '100', 'sale_price': '150', 'low_stock_threshold': '2',
        'category_id': '', 'supplier_id': ''})
    p = fresh(Product, p.id)
    assert p.category_id is None and p.supplier_id is None


def test_product_cannot_use_other_tenant_category_or_supplier(client, shop):
    other = make_tenant('Otro')
    foreign_cat, foreign_sup = make_cat(other, 'Ajena'), make_sup(other, 'Ajeno')
    login(client, shop['owner'])
    r = new_product(client, category_id=str(foreign_cat.id))
    assert r.status_code == 400
    r = new_product(client, supplier_id=str(foreign_sup.id))
    assert r.status_code == 400
    r = new_product(client, category_id='abc')
    assert r.status_code == 400
    assert Product.query.filter_by(name='Gaseosa').count() == 0


def test_db_rejects_cross_tenant_category_on_product(shop):
    other = make_tenant('Otro')
    foreign = make_cat(other, 'Ajena')
    p = shop['product']
    p.category_id = foreign.id
    if db.engine.dialect.name == 'sqlite':
        pytest.skip('SQLite no aplica la FK compuesta por defecto; se valida en Postgres (CI)')
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_inventory_filters_and_columns(client, shop):
    cat, sup = make_cat(shop['tenant']), make_sup(shop['tenant'])
    a = make_product(shop['tenant'], 'Coca', category_id=cat.id, supplier_id=sup.id)
    make_product(shop['tenant'], 'Detergente')
    login(client, shop['owner'])
    page = client.get(f'/app/inventory/productos?category={cat.id}').data
    assert b'Coca' in page and b'Detergente' not in page and b'Yerba' not in page
    assert b'Detergente' in client.get('/app/inventory/productos?category=0').data      # sin categoría
    assert b'Detergente' not in client.get(f'/app/inventory/productos?supplier={sup.id}').data
    assert a.name.encode() in client.get('/app/inventory/productos').data


def test_employee_does_not_see_suppliers(client, shop):
    sup = make_sup(shop['tenant'], 'ProveedorSecreto')
    make_product(shop['tenant'], 'Coca', supplier_id=sup.id)
    login(client, shop['employee'])
    page = client.get('/app/inventory/productos').data
    assert b'Coca' in page and b'ProveedorSecreto' not in page
    page = client.get(f'/app/inventory/productos?supplier={sup.id}').data         # el filtro se ignora
    assert b'Yerba' in page


# ── precios por categoría ──────────────────────────────────
def test_price_update_by_category(client, shop):
    cat = make_cat(shop['tenant'])
    inside = make_product(shop['tenant'], 'Coca', price='100', category_id=cat.id)
    outside = shop['product']                                                     # precio 150, sin categoría
    login(client, shop['owner'])
    form = {'direction': 'up', 'percent': '10', 'applies_to': 'sale', 'rounding': 'none',
            'scope': 'category', 'category_id': str(cat.id)}
    page = client.post(PRICES + '/vista-previa', data=form)
    assert page.status_code == 200 and b'Bebidas' in page.data
    client.post(PRICES + '/aplicar', data=form)
    assert fresh(Product, inside.id).sale_price == Decimal('110.00')
    assert fresh(Product, outside.id).sale_price == Decimal('150.00')


def test_price_update_by_category_requires_valid_category(client, shop):
    other = make_tenant('Otro')
    foreign = make_cat(other, 'Ajena')
    login(client, shop['owner'])
    base = {'direction': 'up', 'percent': '10', 'applies_to': 'sale', 'rounding': 'none', 'scope': 'category'}
    assert client.post(PRICES + '/vista-previa', data={**base, 'category_id': ''}).status_code == 400
    assert client.post(PRICES + '/vista-previa', data={**base, 'category_id': str(foreign.id)}).status_code == 400
    client.post(PRICES + '/aplicar', data={**base, 'category_id': str(foreign.id)})
    assert fresh(Product, shop['product'].id).sale_price == Decimal('150.00')


# ── proveedores ────────────────────────────────────────────
def test_supplier_crud_and_isolation(client, shop):
    other = make_tenant('Otro')
    foreign = make_sup(other, 'Ajeno')
    login(client, shop['owner'])
    client.post(SUP + '/nuevo', data={'name': 'Coca', 'phone': '11 5555', 'email': 'c@x.com', 'notes': 'martes'})
    sup = Supplier.query.filter_by(tenant_id=shop['tenant'].id).one()
    sup_id = sup.id                      # el objeto deja de ser válido cuando se borra
    assert sup.phone == '11 5555' and sup.email == 'c@x.com'
    client.post(SUP + '/nuevo', data={'name': 'COCA'})                            # duplicado
    assert Supplier.query.filter_by(tenant_id=shop['tenant'].id).count() == 1
    client.post(SUP + '/nuevo', data={'name': 'Mal', 'email': 'no-es-email'})
    assert Supplier.query.filter_by(tenant_id=shop['tenant'].id).count() == 1
    client.post(f'{SUP}/{sup_id}/editar', data={'name': 'Coca-Cola'})
    assert fresh(Supplier, sup_id).name == 'Coca-Cola' and fresh(Supplier, sup_id).phone is None
    assert client.get(SUP).status_code == 200 and b'Coca-Cola' in client.get(SUP).data
    assert client.get(f'{SUP}/{foreign.id}/editar').status_code == 404
    client.post(f'{SUP}/{foreign.id}/eliminar')
    assert fresh(Supplier, foreign.id) is not None
    client.post(f'{SUP}/{sup_id}/eliminar')
    assert fresh(Supplier, sup_id) is None


def test_deleting_supplier_keeps_products(client, shop):
    sup = make_sup(shop['tenant'])
    p = make_product(shop['tenant'], 'Coca', supplier_id=sup.id)
    login(client, shop['owner'])
    client.post(f'{SUP}/{sup.id}/eliminar')
    assert fresh(Product, p.id).supplier_id is None


# ── exportación y borrado de negocio ───────────────────────
def test_export_includes_category_and_supplier(client, shop):
    cat, sup = make_cat(shop['tenant'], 'Bebidas'), make_sup(shop['tenant'], 'Coca')
    make_product(shop['tenant'], 'Gaseosa', category_id=cat.id, supplier_id=sup.id)
    login(client, shop['owner'])
    text = client.get('/app/exportar/descargar/productos?formato=csv').data.decode('utf-8-sig')
    assert 'Categoría;Proveedor' in text and 'Gaseosa;;Bebidas;Coca;' in text


def test_delete_business_removes_catalog(shop):
    tid = shop['tenant'].id
    cat, sup = make_cat(shop['tenant']), make_sup(shop['tenant'])
    shop['product'].category_id, shop['product'].supplier_id = cat.id, sup.id
    db.session.commit()
    delete_tenant(shop['tenant'])
    assert Category.query.filter_by(tenant_id=tid).count() == 0
    assert Supplier.query.filter_by(tenant_id=tid).count() == 0


def test_selling_still_works_with_categories(client, shop):
    """Regresión: la carga de categorías no debe romper el bloqueo de filas (FOR UPDATE) al vender."""
    cat = make_cat(shop['tenant'])
    p = make_product(shop['tenant'], 'Coca', category_id=cat.id, stock=5)
    login(client, shop['employee'])
    r = client.post('/app/pos/api/sale', json={'payment_method': 'cash', 'items': [{'product_id': p.id, 'quantity': 2}]})
    assert r.status_code == 200 and fresh(Product, p.id).stock == 3