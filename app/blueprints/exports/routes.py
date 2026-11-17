from datetime import timedelta

from flask import Response, render_template, request
from flask_login import current_user

from . import exports_bp
from ...extensions import limiter
from ...services import exports as svc
from ...utils.decorators import login_required_with_tenant, require
from ...utils.permissions import INVENTORY_MANAGE, REPORTS_VIEW
from ...utils.timeutils import local_today, parse_local_date
from ...utils.xlsx import build_csv, build_xlsx

XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
KINDS = ('productos', 'ventas', 'movimientos')


@exports_bp.route('/')
@login_required_with_tenant
@require(REPORTS_VIEW)
def index():
    today = local_today()
    return render_template('exports/index.html', today=today, month_ago=today - timedelta(days=30),
                           can_costs=current_user.can(INVENTORY_MANAGE))


@exports_bp.route('/descargar/<kind>')
@login_required_with_tenant
@require(REPORTS_VIEW)
@limiter.limit('20 per hour')
def download(kind):
    if kind not in KINDS:
        return Response('Tipo de exportación inválido.', status=404)
    fmt = 'csv' if request.args.get('formato') == 'csv' else 'xlsx'
    today = local_today()
    end = parse_local_date(request.args.get('hasta'), default=today)
    start = parse_local_date(request.args.get('desde'), default=today - timedelta(days=30))
    if start > end:
        start, end = end, start
    tid = current_user.tenant_id

    if kind == 'productos':
        # Los costos solo los ve quien puede gestionar el inventario.
        base, cols, rows = svc.products_dataset(tid, current_user.can(INVENTORY_MANAGE))
        label = 'Productos'
    elif kind == 'ventas':
        base, cols, rows = svc.sales_dataset(tid, start, end, request.args.get('anuladas') == '1')
        label = 'Ventas'
    else:
        base, cols, rows = svc.movements_dataset(tid, start, end)
        label = 'Movimientos'

    filename = f'fivox-{base}-{today.isoformat()}.{fmt}'
    if fmt == 'csv':
        body, mime = build_csv(cols, rows), 'text/csv; charset=utf-8'
    else:
        body, mime = build_xlsx(label, cols, rows), XLSX_MIME
    return Response(body, mimetype=mime, headers={
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Cache-Control': 'no-store'})
