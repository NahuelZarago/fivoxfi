from datetime import timedelta

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from . import reports_bp
from ...models.sale import Sale
from ...services import metrics
from ...services.sales import void_sale
from ...utils.decorators import login_required_with_tenant, require
from ...utils.permissions import REPORTS_VIEW, SALES_VOID
from ...utils.timeutils import local_day_bounds_utc, local_today, parse_local_date
from ...utils.validation import ValidationFailure, clean_text


@reports_bp.route('/cierre-diario')
@login_required_with_tenant
@require(REPORTS_VIEW)
def daily_close():
    today = local_today()
    day = parse_local_date(request.args.get('fecha'), default=today)
    start, end = local_day_bounds_utc(day)
    close = metrics.close_for_day(current_user.tenant_id, start, end)
    return render_template('reports/daily_close.html', close=close, day=day, today=today,
                           prev_day=day - timedelta(days=1),
                           next_day=day + timedelta(days=1) if day < today else None)


@reports_bp.route('/historial-ventas')
@login_required_with_tenant
@require(REPORTS_VIEW)
def sales_history():
    page = request.args.get('page', 1, type=int)
    sales = (Sale.query.filter_by(tenant_id=current_user.tenant_id)
             .order_by(Sale.created_at.desc(), Sale.id.desc())
             .paginate(page=page, per_page=20, error_out=False))
    return render_template('reports/sales_history.html', sales=sales)


@reports_bp.route('/ventas/<int:sale_id>/anular', methods=['POST'])
@login_required_with_tenant
@require(SALES_VOID)
def sale_void(sale_id):
    try:
        reason = clean_text(request.form.get('reason', ''), 'Motivo', max_len=200, required=False)
        void_sale(current_user.tenant_id, sale_id, current_user.id, reason)
        flash(f'Venta #{sale_id} anulada y stock devuelto.', 'success')
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('reports.sales_history', page=request.form.get('page', 1, type=int)))
