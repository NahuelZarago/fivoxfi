"""Tests de módulos puros: no necesitan base de datos ni extensiones de Flask."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from flask import Flask, jsonify, request

from app.utils import codes, formatting, nav, permissions as perm, timeutils
from app.utils.csrf import csrf_exempt, init_csrf
from app.utils.text import escape_like, slugify
from app.utils.urls import safe_next_url
from app.utils.validation import (
    ValidationFailure, clean_text, parse_int, parse_money, password_checks, validate_email, validate_password)


# ── dinero ──────────────────────────────────────────────────
@pytest.mark.parametrize('raw,expected', [
    ('10', '10.00'), ('10,5', '10.50'), ('10.50', '10.50'), ('1.234,50', '1234.50'),
    ('0', '0.00'), (' 99 ', '99.00'),
])
def test_parse_money_ok(raw, expected):
    assert parse_money(raw) == Decimal(expected)


@pytest.mark.parametrize('raw', ['', 'abc', '-1', 'NaN', 'inf', '1,234', '10.999', '1e5', '999999999', None])
def test_parse_money_rejects(raw):
    with pytest.raises(ValidationFailure):
        parse_money(raw)


def test_format_money():
    assert formatting.format_money(Decimal('1234.5')) == '$1.234,50'
    assert formatting.format_money(0) == '$0,00'
    assert formatting.format_money(None) == '$0,00'
    assert formatting.format_money0(Decimal('1234.6')) == '$1.235'


def test_parse_int():
    assert parse_int('5', 'x') == 5
    for bad in ['', '1.5', 'a', '99999999999', '-1']:
        with pytest.raises(ValidationFailure):
            parse_int(bad, 'x')
    assert parse_int('-3', 'x', minimum=-10) == -3


# ── validaciones ───────────────────────────────────────────
def test_email_and_password():
    assert validate_email(' A@B.com ') == 'a@b.com'
    for bad in ['', 'x', 'a@b', 'a b@c.com']:
        with pytest.raises(ValidationFailure):
            validate_email(bad)
    validate_password('abcdefg1')
    for bad in ['short1', 'abcdefgh', '12345678', 'a1' * 100]:
        with pytest.raises(ValidationFailure):
            validate_password(bad)


def test_clean_text():
    assert clean_text('  hola   mundo\n', 'x') == 'hola mundo'
    assert clean_text('', 'x', required=False) is None
    with pytest.raises(ValidationFailure):
        clean_text('a' * 300, 'x')


# ── tiempo (UTC-3) ─────────────────────────────────────────
def test_local_midnight_boundaries():
    # 02:00 UTC del 10/mar = 23:00 del 9/mar en Argentina -> el "día" empezó 03:00 UTC del 9/mar
    now = datetime(2026, 3, 10, 2, 0)
    assert timeutils.local_midnight_utc(now=now) == datetime(2026, 3, 9, 3, 0)
    # 04:00 UTC del 10/mar = 01:00 del 10/mar local
    assert timeutils.local_midnight_utc(now=datetime(2026, 3, 10, 4, 0)) == datetime(2026, 3, 10, 3, 0)


def test_month_start_and_day_bounds():
    assert timeutils.local_month_start_utc(now=datetime(2026, 3, 1, 2, 0)) == datetime(2026, 2, 1, 3, 0)
    start, end = timeutils.local_day_bounds_utc(date(2026, 5, 20))
    assert start == datetime(2026, 5, 20, 3, 0) and end - start == timedelta(days=1)
    assert timeutils.parse_local_date('2026-05-20') == date(2026, 5, 20)
    assert timeutils.parse_local_date('basura', default=date(2000, 1, 1)) == date(2000, 1, 1)


def test_format_local_dt():
    assert formatting.format_local_dt(datetime(2026, 3, 10, 2, 5)) == '09/03/2026 23:05'
    assert formatting.format_local_dt(None) == '—'


# ── códigos ────────────────────────────────────────────────
def test_codes():
    e, c = codes.generate_employee_code(), codes.generate_client_code()
    assert e.startswith('FX-') and len(e) == 9 and c.startswith('FC-')
    assert codes.normalize_code(' fx a3k9b2 ') == 'FX-A3K9B2'
    assert codes.normalize_code('FC-A3K9B2') == 'FC-A3K9B2'
    for bad in ['', None, 'XX-123456', 'FX-12', "FX-'; DROP"]:
        assert codes.normalize_code(bad) is None
    assert len({codes.generate_employee_code() for _ in range(200)}) > 190


# ── urls ───────────────────────────────────────────────────
@pytest.mark.parametrize('target', [
    'https://evil.com', '//evil.com', '/\\evil.com', '/\t/evil.com', '/\n/evil.com',
    'javascript:alert(1)', '', None, 'evil.com', '/ok\r\nSet-Cookie: x=1'])
def test_safe_next_rejects(target):
    assert safe_next_url(target, '/fallback') == '/fallback'


def test_safe_next_accepts():
    assert safe_next_url('/app/pos/terminal?x=1', '/f') == '/app/pos/terminal?x=1'


# ── texto ──────────────────────────────────────────────────
def test_text():
    assert slugify('Kiosco "Don Pepe" ñandú!') == 'kiosco-don-pepe-nandu'
    assert slugify('!!!') == 'negocio'
    assert len(slugify('a' * 200)) <= 60
    assert escape_like('50%_off\\') == '50\\%\\_off\\\\'


# ── permisos ───────────────────────────────────────────────
def test_permission_matrix():
    for cap in perm.ROLE_CAPABILITIES[perm.ROLE_OWNER]:
        assert perm.can(perm.ROLE_OWNER, cap)
    assert perm.can('employee', perm.POS_SELL) and perm.can('employee', perm.STOCK_ENTRY)
    for cap in (perm.REPORTS_VIEW, perm.SALES_VOID, perm.STOCK_ADJUST, perm.TEAM_MANAGE,
                perm.INVENTORY_MANAGE, perm.APPOINTMENTS_VIEW):
        assert not perm.can('employee', cap)
    assert perm.can('client', perm.APPOINTMENTS_VIEW) and not perm.can('client', perm.POS_SELL)
    assert not perm.can(None, perm.POS_SELL) and not perm.can('hacker', perm.POS_SELL)
    with pytest.raises(ValueError):
        perm.can('owner', 'typo.capability')
    assert perm.home_endpoint('client') == 'appointments.index'


def test_nav_per_role():
    def keys(role):
        return [i['key'] for g in nav.build_nav(role, 'dashboard.index') for i in g['items']]
    assert 'team' in keys('owner') and 'reports' in keys('owner') and 'movements' in keys('owner')
    emp = keys('employee')
    assert 'pos' in emp and 'inventory' in emp and 'reports' not in emp and 'team' not in emp and 'panel' not in emp
    cl = keys('client')
    assert 'appointments' in cl and 'pos' not in cl and 'inventory' not in cl
    groups = nav.build_nav('owner', 'appointments.index')
    appt = [i for g in groups for i in g['items'] if i['key'] == 'appointments'][0]
    assert appt['active'] and appt['status'] == 'maintenance'
    inv = [i for g in nav.build_nav('owner', 'inventory.product_list', {'inventory': 3}) for i in g['items']
           if i['key'] == 'inventory'][0]
    assert inv['active'] and inv['badge'] == 3
    mov = [i for g in nav.build_nav('owner', 'inventory.movement_list') for i in g['items'] if i['key'] == 'movements'][0]
    assert mov['active']


# ── CSRF (app Flask mínima) ────────────────────────────────
@pytest.fixture()
def csrf_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='k' * 40, CSRF_ENABLED=True, TESTING=True)
    init_csrf(app)

    @app.get('/form')
    def form():
        from flask import render_template_string
        return render_template_string('{{ csrf_input() }}|{{ csrf_token() }}')

    @app.post('/act')
    def act():
        return 'done'

    @app.post('/hook')
    @csrf_exempt
    def hook():
        return 'hooked'
    return app


def _token(client):
    import re
    body = client.get('/form').get_data(as_text=True)
    return re.search(r'value="([^"]+)"', body).group(1)


def test_csrf_blocks_without_token(csrf_app):
    c = csrf_app.test_client()
    assert c.post('/act').status_code == 400
    c.get('/form')
    assert c.post('/act', data={'csrf_token': 'wrong'}).status_code == 400


def test_csrf_accepts_form_and_header(csrf_app):
    c = csrf_app.test_client()
    t = _token(c)
    assert c.post('/act', data={'csrf_token': t}).status_code == 200
    assert c.post('/act', headers={'X-CSRFToken': t}).status_code == 200


def test_csrf_exempt_and_safe_methods(csrf_app):
    c = csrf_app.test_client()
    assert c.post('/hook').status_code == 200
    assert c.get('/form').status_code == 200


def test_csrf_disabled_in_testing_config():
    app = Flask(__name__)
    app.config.update(SECRET_KEY='k' * 40, CSRF_ENABLED=False)
    init_csrf(app)

    @app.post('/x')
    def x():
        return 'ok'
    assert app.test_client().post('/x').status_code == 200


def test_password_checks():
    score, c = password_checks('')
    assert score == 0 and not any(c.values())
    score, c = password_checks('abc')
    assert score == 1 and c['lower'] and not c['length']
    score, c = password_checks('Clave1234')
    assert c['length'] and c['upper'] and c['lower'] and c['digit'] and not c['symbol'] and not c['long']
    score, c = password_checks('Clave-Muy-Larga-1234!')
    assert score == 6


# ── v4: precios, xlsx, csv ────────────────────────────────
def test_parse_percent():
    from decimal import Decimal
    from app.utils.validation import ValidationFailure, parse_percent
    assert parse_percent('8') == Decimal('8')
    assert parse_percent(' 10,5 ') == Decimal('10.5')
    assert parse_percent('-10') == Decimal('-10')
    for bad in ('', 'abc', '0', '-95', '501', '1e2', '8%', '--3'):
        with pytest.raises(ValidationFailure):
            parse_percent(bad)


def test_compute_new_price():
    from decimal import Decimal
    from app.utils.pricing import compute_new_price
    assert compute_new_price('100.00', Decimal('8')) == Decimal('108.00')
    assert compute_new_price('10.05', Decimal('10')) == Decimal('11.06')       # 11.055 -> mitad hacia arriba
    assert compute_new_price('150', Decimal('-10')) == Decimal('135.00')
    assert compute_new_price('1234.00', Decimal('8'), Decimal('10')) == Decimal('1330.00')   # 1332.72 -> 1330
    assert compute_new_price('1234.00', Decimal('8'), Decimal('100')) == Decimal('1300.00')
    assert compute_new_price('0', Decimal('50')) == Decimal('0.00')


def test_xlsx_roundtrip_and_formula_safety():
    openpyxl = pytest.importorskip('openpyxl')
    import io
    from datetime import datetime
    from decimal import Decimal
    from app.utils.xlsx import DATETIME, INT, MONEY, TEXT, build_xlsx
    cols = [('Nombre', TEXT, 20), ('Precio', MONEY, 10), ('Stock', INT, 8), ('Fecha', DATETIME, 18)]
    data = build_xlsx('Hoja/1', cols, [['=HYPERLINK("x")<b>', Decimal('1234.50'), 3, datetime(2026, 3, 1, 10, 30)], ['Ñandú', Decimal('0'), 0, None]])
    ws = openpyxl.load_workbook(io.BytesIO(data)).active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ('Nombre', 'Precio', 'Stock', 'Fecha')
    assert rows[1][0] == '=HYPERLINK("x")<b>' and ws['A2'].data_type == 's'    # texto, no fórmula
    assert rows[1][1] == 1234.5 and rows[1][2] == 3 and rows[1][3] == datetime(2026, 3, 1, 10, 30)
    assert rows[2][0] == 'Ñandú'
    assert ws.freeze_panes == 'A2' and ws.auto_filter.ref == 'A1:D3'


def test_xlsx_strips_control_chars():
    from app.utils.xlsx import TEXT, build_xlsx
    import zipfile, io
    data = build_xlsx('x', [('A', TEXT, 5)], [['ok\x00\x08bad']])
    assert b'\x00' not in zipfile.ZipFile(io.BytesIO(data)).read('xl/worksheets/sheet1.xml')


def test_csv_format_and_injection():
    from decimal import Decimal
    from app.utils.xlsx import MONEY, TEXT, build_csv
    out = build_csv([('Nombre', TEXT, 5), ('Precio', MONEY, 5)], [['=SUM(A1)', Decimal('1234.5')], ['Té', Decimal('2')]])
    assert out.startswith(b'\xef\xbb\xbf')
    text = out.decode('utf-8-sig').splitlines()
    assert text[0] == 'Nombre;Precio'
    assert text[1] == "'=SUM(A1);1234,50"
    assert text[2] == 'Té;2,00'
