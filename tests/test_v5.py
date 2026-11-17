"""v5: caja diaria (apertura/cierre con arqueo) y tickets."""
from decimal import Decimal

import pytest

for _dep in ("flask_sqlalchemy", "flask_login", "flask_limiter", "flask_migrate", "flask_mail"):
    pytest.importorskip(_dep)

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import CashSession, Sale
from app.services.sales import void_sale
from app.services.tenants import delete_tenant

from .helpers import login, make_product, make_tenant, make_user


def sell(client, product, qty=1, method='cash'):
    r = client.post('/app/pos/api/sale', json={'payment_method': method, 'items': [{'product_id': product.id, 'quantity': qty}]})
    assert r.status_code == 200, r.data
    return r.get_json()['sale_id']


def fresh_session(session_id):
    db.session.expire_all()
    return db.session.get(CashSession, session_id)


def test_open_and_single_open_session(client, shop):
    login(client, shop['employee'])
    client.post('/app/caja/abrir', data={'opening_amount': '1000'})
    assert CashSession.query.filter_by(closed_at=None).count() == 1
    client.post('/app/caja/abrir', data={'opening_amount': '500'})       # segunda: rechazada
    assert CashSession.query.count() == 1


@pytest.mark.parametrize('bad', ['', 'abc', '-5', '1e3'])
def test_open_rejects_bad_amount(client, shop, bad):
    login(client, shop['employee'])
    client.post('/app/caja/abrir', data={'opening_amount': bad})
    assert CashSession.query.count() == 0


def test_db_forbids_two_open_sessions_per_tenant(shop):
    tid = shop['tenant'].id
    db.session.add(CashSession(tenant_id=tid, opening_amount=Decimal('0')))
    db.session.commit()
    db.session.add(CashSession(tenant_id=tid, opening_amount=Decimal('0')))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_other_tenant_can_have_its_own_open_session(shop):
    other = make_tenant('Otro')
    for tid in (shop['tenant'].id, other.id):
        db.session.add(CashSession(tenant_id=tid, opening_amount=Decimal('0')))
    db.session.commit()
    assert CashSession.query.count() == 2


def test_close_computes_expected_from_cash_sales_only(client, shop):
    p = shop['product']                       # precio de venta 150
    login(client, shop['employee'])
    client.post('/app/caja/abrir', data={'opening_amount': '1000'})
    sell(client, p, 2, 'cash')                # +300
    sell(client, p, 1, 'card')                # no es efectivo
    client.post('/app/caja/cerrar', data={'counted_cash': '1290', 'note': 'faltaron 10'})
    c = CashSession.query.one()
    c = fresh_session(c.id)
    assert c.closed_at is not None
    assert c.expected_cash == Decimal('1300.00') and c.counted_cash == Decimal('1290.00')
    assert c.difference == Decimal('-10.00') and c.note == 'faltaron 10'


def test_voided_sales_do_not_count(client, shop):
    p = shop['product']
    login(client, shop['employee'])
    client.post('/app/caja/abrir', data={'opening_amount': '0'})
    sale_id = sell(client, p, 2, 'cash')
    void_sale(shop['tenant'].id, sale_id, shop['owner'].id, 'error')
    client.post('/app/caja/cerrar', data={'counted_cash': '0'})
    assert CashSession.query.one().expected_cash == Decimal('0.00')


def test_sales_before_opening_are_not_counted(client, shop):
    login(client, shop['employee'])
    sell(client, shop['product'], 1, 'cash')
    client.post('/app/caja/abrir', data={'opening_amount': '200'})
    client.post('/app/caja/cerrar', data={'counted_cash': '200'})
    assert CashSession.query.one().expected_cash == Decimal('200.00')


def test_close_without_open_session_is_harmless(client, shop):
    login(client, shop['employee'])
    r = client.post('/app/caja/cerrar', data={'counted_cash': '10'})
    assert r.status_code == 302 and CashSession.query.count() == 0


def test_cannot_close_twice(client, shop):
    login(client, shop['employee'])
    client.post('/app/caja/abrir', data={'opening_amount': '0'})
    client.post('/app/caja/cerrar', data={'counted_cash': '0'})
    first = CashSession.query.one().closed_at
    client.post('/app/caja/cerrar', data={'counted_cash': '999'})
    assert fresh_session(CashSession.query.one().id).closed_at == first
    assert CashSession.query.one().counted_cash == Decimal('0.00')


def test_pages_render_for_owner_and_employee(client, shop):
    login(client, shop['owner'])
    assert client.get('/app/caja/').status_code == 200
    client.post('/app/caja/abrir', data={'opening_amount': '100'})
    assert b'Cerrar caja' in client.get('/app/caja/').data
    client.post('/app/caja/cerrar', data={'counted_cash': '100'})
    sid = CashSession.query.one().id
    assert client.get(f'/app/caja/{sid}').status_code == 200
    assert b'Cierres anteriores' in client.get('/app/caja/').data
    client.post('/auth/logout')
    login(client, shop['employee'])
    r = client.get('/app/caja/')
    assert r.status_code == 200 and b'Cierres anteriores' not in r.data


def test_employee_cannot_see_history_detail(client, shop):
    c = CashSession(tenant_id=shop['tenant'].id, opening_amount=Decimal('0'))
    db.session.add(c)
    db.session.commit()
    login(client, shop['employee'])
    assert client.get(f'/app/caja/{c.id}').status_code == 403


def test_client_role_cannot_use_cash(client, shop):
    login(client, shop['client'])
    assert client.get('/app/caja/').status_code == 403
    assert client.post('/app/caja/abrir', data={'opening_amount': '1'}).status_code == 403


def test_cash_detail_isolated_between_tenants(client, shop):
    other = make_tenant('Otro')
    c = CashSession(tenant_id=other.id, opening_amount=Decimal('0'))
    db.session.add(c)
    db.session.commit()
    login(client, shop['owner'])
    assert client.get(f'/app/caja/{c.id}').status_code == 404


def test_pos_banner_depends_on_cash_state(client, shop):
    login(client, shop['employee'])
    assert b'La caja est' in client.get('/app/pos/terminal').data
    client.post('/app/caja/abrir', data={'opening_amount': '0'})
    assert b'La caja est' not in client.get('/app/pos/terminal').data


def test_delete_business_removes_cash_sessions(client, shop):
    tid = shop['tenant'].id
    db.session.add(CashSession(tenant_id=tid, opening_amount=Decimal('0')))
    db.session.commit()
    delete_tenant(shop['tenant'])
    assert CashSession.query.filter_by(tenant_id=tid).count() == 0


# ── tickets ────────────────────────────────────────────────
def test_ticket_content_and_autoprint(client, shop):
    login(client, shop['employee'])
    sid = sell(client, shop['product'], 2)
    r = client.get(f'/app/pos/ticket/{sid}')
    assert r.status_code == 200 and b'Yerba' in r.data and b'Kiosco' in r.data and b'window.print()' in r.data
    assert b'addEventListener' not in r.data                       # sin ?print=1 no imprime solo
    assert b'addEventListener' in client.get(f'/app/pos/ticket/{sid}?print=1').data


def test_ticket_access_rules(client, shop):
    other_emp = make_user(shop['tenant'], 'employee', email='emp2@t.com')
    login(client, shop['employee'])
    sid = sell(client, shop['product'])
    client.post('/auth/logout')
    login(client, other_emp)
    assert client.get(f'/app/pos/ticket/{sid}').status_code == 404      # venta de otro empleado
    client.post('/auth/logout')
    login(client, shop['owner'])
    assert client.get(f'/app/pos/ticket/{sid}').status_code == 200      # el dueño ve todas
    client.post('/auth/logout')
    login(client, shop['client'])
    assert client.get(f'/app/pos/ticket/{sid}').status_code == 403


def test_ticket_isolated_between_tenants(client, shop):
    other = make_tenant('Otro')
    owner2 = make_user(other, 'owner', email='o2@t.com')
    p2 = make_product(other, 'Ajeno')
    login(client, owner2)
    sid = sell(client, p2)
    client.post('/auth/logout')
    login(client, shop['owner'])
    assert client.get(f'/app/pos/ticket/{sid}').status_code == 404


def test_ticket_requires_login(client, shop):
    assert client.get('/app/pos/ticket/1').status_code == 302


def test_voided_ticket_is_marked(client, shop):
    login(client, shop['employee'])
    sid = sell(client, shop['product'])
    void_sale(shop['tenant'].id, sid, shop['owner'].id, 'x')
    assert b'VENTA ANULADA' in client.get(f'/app/pos/ticket/{sid}').data


# ── impresión del cierre ───────────────────────────────────
def test_print_closed_session_rules(client, shop):
    emp2 = make_user(shop['tenant'], 'employee', email='emp2@t.com')
    login(client, shop['employee'])
    client.post('/app/caja/abrir', data={'opening_amount': '1000'})
    r = client.post('/app/caja/cerrar', data={'counted_cash': '900', 'note': 'nota'})
    sid = CashSession.query.one().id
    assert r.headers['Location'].endswith(f'/app/caja/{sid}/imprimir')          # el empleado va directo al comprobante
    page = client.get(f'/app/caja/{sid}/imprimir')
    assert page.status_code == 200 and b'CIERRE DE CAJA' in page.data and b'Falta efectivo' in page.data
    assert b'addEventListener' not in page.data and b'addEventListener' in client.get(f'/app/caja/{sid}/imprimir?print=1').data
    client.post('/auth/logout')
    login(client, emp2)
    assert client.get(f'/app/caja/{sid}/imprimir').status_code == 404          # no es suyo
    client.post('/auth/logout')
    login(client, shop['owner'])
    assert client.get(f'/app/caja/{sid}/imprimir').status_code == 200
    assert b'Imprimir cierre' in client.get(f'/app/caja/{sid}').data


def test_cannot_print_open_or_foreign_session(client, shop):
    other = make_tenant('Otro')
    foreign = CashSession(tenant_id=other.id, opening_amount=Decimal('0'))
    mine = CashSession(tenant_id=shop['tenant'].id, opening_amount=Decimal('0'))
    db.session.add_all([foreign, mine])
    db.session.commit()
    login(client, shop['owner'])
    assert client.get(f'/app/caja/{foreign.id}/imprimir').status_code == 404
    assert client.get(f'/app/caja/{mine.id}/imprimir').status_code == 404       # sigue abierta
