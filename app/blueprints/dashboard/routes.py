from flask import render_template
from flask_login import current_user
from . import dashboard_bp
from ...utils.decorators import login_required_with_tenant
from ...models.product import Product
from ...models.sale import Sale
from datetime import datetime, timedelta
from sqlalchemy import func
from ...extensions import db


@dashboard_bp.route('/')
@login_required_with_tenant
def index():
    tenant_id = current_user.tenant_id

    # Métricas rápidas para el panel
    total_products = Product.query.filter_by(tenant_id=tenant_id, is_active=True).count()
    low_stock_count = Product.query.filter(
        Product.tenant_id == tenant_id,
        Product.is_active == True,
        Product.stock <= 5
    ).count()

    # Ventas de hoy
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.tenant_id == tenant_id,
        Sale.created_at >= today_start
    ).scalar() or 0

    today_profit = db.session.query(
        func.sum(Sale.total_amount - Sale.total_cost)
    ).filter(
        Sale.tenant_id == tenant_id,
        Sale.created_at >= today_start
    ).scalar() or 0

    return render_template(
        'dashboard/index.html',
        total_products=total_products,
        low_stock_count=low_stock_count,
        today_sales=float(today_sales),
        today_profit=float(today_profit)
    )
