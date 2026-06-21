from flask import render_template, request
from flask_login import current_user
from . import reports_bp
from ...extensions import db
from ...models.sale import Sale
from ...utils.decorators import login_required_with_tenant, admin_required
from datetime import datetime, timedelta
from sqlalchemy import func


@reports_bp.route('/cierre-diario')
@login_required_with_tenant
@admin_required
def daily_close():
    """RF-13: Reporte de caja de las últimas 24 horas, desglosado por método de pago."""
    since = datetime.utcnow() - timedelta(hours=24)

    results = db.session.query(
        Sale.payment_method,
        func.sum(Sale.total_amount).label('total'),
        func.sum(Sale.total_amount - Sale.total_cost).label('profit'),
        func.count(Sale.id).label('count')
    ).filter(
        Sale.tenant_id == current_user.tenant_id,
        Sale.created_at >= since
    ).group_by(Sale.payment_method).all()

    grand_total = sum(r.total for r in results)
    grand_profit = sum(r.profit for r in results)

    return render_template(
        'reports/daily_close.html',
        results=results,
        grand_total=float(grand_total or 0),
        grand_profit=float(grand_profit or 0),
        since=since
    )


@reports_bp.route('/historial-ventas')
@login_required_with_tenant
@admin_required
def sales_history():
    """RF-15: Historial de ventas con paginación."""
    page = request.args.get('page', 1, type=int)

    sales = Sale.query.filter_by(
        tenant_id=current_user.tenant_id
    ).order_by(Sale.created_at.desc()).paginate(page=page, per_page=20)

    return render_template('reports/sales_history.html', sales=sales)
