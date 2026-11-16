"""
Renderiza las plantillas en una app Flask mínima (sin base de datos) con datos de prueba,
para detectar errores de variables/filtros que el análisis estático no ve.
Uso: python tests/render_check.py
"""
import glob, os, re, sys, ast
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace as NS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); os.chdir(ROOT)

from flask import Flask, render_template
from jinja2 import ChoiceLoader, FileSystemLoader
from app.utils import formatting, nav
from app.utils.csrf import init_csrf

app = Flask('app', root_path=os.path.join(ROOT, 'app'))
app.config.update(SECRET_KEY='x' * 40, CSRF_ENABLED=True)
app.jinja_loader = ChoiceLoader([FileSystemLoader(['app/templates'] + glob.glob('app/blueprints/*/templates'))])
init_csrf(app)

# endpoints falsos con los mismos nombres que la app real
for rf in glob.glob('app/blueprints/*/routes.py'):
    bp = rf.split(os.sep)[2]
    src = open(rf).read()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.FunctionDef):
            for d in n.decorator_list:
                if isinstance(d, ast.Call) and getattr(d.func, 'attr', '') == 'route':
                    rule = f'/{bp}/{n.name}'
                    rule += ''.join(f'/<{c}>' for c in re.findall(r'<(?:int:)?(\w+)>', d.args[0].value))
                    rule = re.sub(r'<(\w+)>', lambda m: '<int:%s>' % m.group(1) if m.group(1).endswith('_id') else m.group(0), rule)
                    app.add_url_rule(rule, f'{bp}.{n.name}', lambda **k: '', methods=['GET', 'POST'])

labels = {'sale': 'Venta', 'purchase': 'Compra / reposición', 'loss': 'Merma', 'adjustment': 'Ajuste', 'sale_void': 'Anulada', 'initial': 'Inicial'}
app.jinja_env.filters.update(
    money=formatting.format_money, money0=formatting.format_money0, local_dt=formatting.format_local_dt,
    reason_label=lambda r: labels.get(r, r), payment_label=lambda m: {'cash': 'Efectivo'}.get(m, m))

tenant = NS(name='Kiosco <b>Pepe</b>', plan='basic', employee_code='FX-A3K9B2', client_code='FC-B4K8C3')

def make_user(role):
    return NS(is_authenticated=True, username='Ana <script>', email='a@b.com', role=role, role_label=role.title(),
              tenant=tenant, tenant_id=1, id=1, is_owner=role == 'owner', can=lambda c: __import__('app.utils.permissions', fromlist=['x']).can(role, c))

state = {'user': make_user('owner')}

@app.context_processor
def ctx():
    u = state['user']
    return {'current_user': u, 'can': u.can, 'nav_groups': nav.build_nav(u.role, 'dashboard.index', {'inventory': 2}),
            'support_whatsapp': '5491100000000', 'use_compiled_css': False, 'current_year': 2026}

class Page:
    def __init__(self, items, page=1, pages=2):
        self.items, self.page, self.pages, self.total = items, page, pages, len(items)
        self.has_prev, self.has_next, self.prev_num, self.next_num = page > 1, page < pages, page - 1, page + 1

prod = lambda **k: NS(**{**dict(id=1, name='Yerba <img src=x onerror=alert(1)>', sku='Y1', cost_price=Decimal('100'), sale_price=Decimal('150.5'),
                              stock=3, low_stock_threshold=5, is_active=True, is_low_stock=True, is_out_of_stock=False,
                              unit_margin=Decimal('50.5'), description='d'), **k})
mv = NS(created_at=datetime(2026, 3, 1, 12), reason='sale', quantity_change=-2, stock_after=3, note='n', sale_id=7, user=NS(username='Ana'))
sale = NS(id=7, created_at=datetime(2026, 3, 1, 12), seller=NS(username='Ana'), items=[NS(quantity=2, product_name='Yerba')], payment_method='cash',
          total_amount=Decimal('301'), net_profit=Decimal('101'), is_voided=False, void_reason=None)
week = [{'label': 'Lun', 'total': Decimal('100'), 'date': date(2026, 3, 1)}] * 7
metrics = {'today': {'income': Decimal('10'), 'profit': Decimal('4'), 'count': 1, 'cost': Decimal('6')},
           'month': {'income': Decimal('100'), 'profit': Decimal('40'), 'count': 5, 'cost': Decimal('60')},
           'week': week, 'top': [{'name': 'Yerba', 'qty': 3, 'revenue': Decimal('9')}], 'low_stock': [prod(), prod(stock=0)],
           'inventory_value': {'cost': Decimal('1'), 'retail': Decimal('2')}}
close = {'rows': [{'method': 'cash', 'total': Decimal('5'), 'profit': Decimal('2'), 'count': 1}], 'total': Decimal('5'), 'profit': Decimal('2'), 'count': 1}
member = NS(id=2, username='Luis', email='l@x.com', role_label='Empleado', is_active=True, is_owner=False)

cases = [
    ('public/index.html', {}, 'owner'), ('public/contact.html', {}, 'owner'), ('public/product_landing.html', {'slug': 's'}, 'owner'),
    ('auth/login.html', {'email': 'a@b.com', 'error': None}, 'owner'), ('auth/login.html', {'email': 'a@b.com', 'error': 'Email o contraseña incorrectos.'}, 'owner'), ('auth/register.html', {'form': {'username': 'x', 'email': 'y'}, 'errors': {}}, 'owner'), ('auth/register.html', {'form': {'username': '', 'email': 'y'}, 'errors': {'username': 'El nombre es obligatorio.', 'email': 'Email inválido', 'password': 'x', 'confirm_password': 'y'}}, 'owner'),
    ('auth/choose_role.html', {}, 'owner'), ('auth/join.html', {}, 'owner'), ('auth/setup_owner.html', {}, 'owner'),
    ('auth/pending_verification.html', {}, 'owner'), ('auth/forgot_password.html', {}, 'owner'), ('auth/reset_password.html', {'token': 't', 'errors': {}}, 'owner'), ('auth/reset_password.html', {'token': 't', 'errors': {'password': 'corta'}}, 'owner'),
    ('email/verify.html', {'username': 'Ana', 'url': 'http://x/y'}, 'owner'), ('email/reset.html', {'username': 'Ana', 'url': 'http://x/y'}, 'owner'),
    ('errors/error.html', {'code': 404, 'title': 'No', 'message': 'm', 'authenticated': True}, 'owner'),
    ('dashboard/index.html', {}, 'owner'), ('dashboard/index.html', {}, 'employee'), ('dashboard/index.html', {}, 'client'),
    ('dashboard/gestion.html', {'m': metrics, 'week_peak': Decimal('100')}, 'owner'),
    ('dashboard/settings.html', {}, 'owner'), ('dashboard/settings.html', {}, 'employee'),
    ('dashboard/employees.html', {'members': [member], 'tenant': tenant}, 'owner'),
    ('inventory/list.html', {'products': Page([prod(), prod(is_active=False)]), 'q': '', 'flt': ''}, 'owner'),
    ('inventory/list.html', {'products': Page([prod()]), 'q': 'a', 'flt': 'low'}, 'employee'),
    ('inventory/form.html', {'product': None, 'form': {}}, 'owner'), ('inventory/form.html', {'product': prod(), 'form': {}}, 'owner'),
    ('inventory/form.html', {'product': None, 'form': {'name': 'zz', 'stock': '4'}}, 'owner'),
    ('inventory/stock.html', {'product': prod(), 'movements': Page([mv])}, 'owner'), ('inventory/stock.html', {'product': prod(), 'movements': Page([mv])}, 'employee'),
    ('inventory/movements.html', {'rows': Page([(mv, 'Yerba')]), 'reason': '', 'reasons': labels}, 'owner'),
    ('pos/terminal.html', {'products': [{'id': 1, 'name': '</script><b>', 'sku': '', 'price': '10.00', 'stock': 3}], 'methods': [('cash', 'Efectivo')]}, 'employee'),
    ('reports/daily_close.html', {'close': close, 'day': date(2026, 3, 1), 'today': date(2026, 3, 2), 'prev_day': date(2026, 2, 28), 'next_day': date(2026, 3, 2)}, 'owner'),
    ('reports/sales_history.html', {'sales': Page([sale])}, 'owner'),
    ('appointments/maintenance.html', {}, 'client'), ('appointments/maintenance.html', {}, 'owner'),
]

fail = 0
with app.test_request_context('/'):
    for tpl, data, role in cases:
        state['user'] = make_user(role)
        try:
            html = render_template(tpl, **data)
            assert html.strip(), 'vacío'
            for bad in ('<img src=x onerror', '<script>alert', 'Ana <script>', '<b>Pepe'):
                assert bad not in html.replace('type="application/json"', ''), f'XSS sin escapar: {bad}'
            if tpl == 'pos/terminal.html':
                assert '</script><b>' not in html, 'tojson no escapó </script>'
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f'FALLA {tpl} [{role}]: {type(e).__name__}: {e}')
print(f'{len(cases) - fail}/{len(cases)} plantillas renderizan bien')
sys.exit(1 if fail else 0)
