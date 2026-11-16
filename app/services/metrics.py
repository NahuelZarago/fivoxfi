from datetime import timedelta
from decimal import Decimal

from sqlalchemy import desc, func

from ..extensions import db
from ..models.product import Product
from ..models.sale import Sale, SaleItem
from ..utils.timeutils import (
    WEEKDAYS_ES, local_midnight_utc, local_month_start_utc, to_local, utcnow)

ZERO = Decimal('0')


def _dec(value):
    return Decimal(value) if value is not None else ZERO


def period_totals(tenant_id, start_utc, end_utc=None):
    q = db.session.query(
        func.coalesce(func.sum(Sale.total_amount), 0),
        func.coalesce(func.sum(Sale.total_cost), 0),
        func.count(Sale.id),
    ).filter(Sale.tenant_id == tenant_id, Sale.voided_at.is_(None), Sale.created_at >= start_utc)
    if end_utc is not None:
        q = q.filter(Sale.created_at < end_utc)
    income, cost, count = q.one()
    income, cost = _dec(income), _dec(cost)
    return {'income': income, 'cost': cost, 'profit': income - cost, 'count': int(count)}


def last_7_days(tenant_id):
    result = []
    for ago in range(6, -1, -1):
        start = local_midnight_utc(days_ago=ago)
        totals = period_totals(tenant_id, start, start + timedelta(days=1))
        local_day = to_local(start)
        result.append({'label': WEEKDAYS_ES[local_day.weekday()], 'date': local_day.date(),
                       'total': totals['income']})
    return result


def top_products(tenant_id, start_utc, limit=5):
    rows = (db.session.query(
        SaleItem.product_name,
        func.sum(SaleItem.quantity).label('qty'),
        func.sum(SaleItem.quantity * SaleItem.unit_sale_price).label('revenue'))
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.tenant_id == tenant_id, Sale.voided_at.is_(None), Sale.created_at >= start_utc)
        .group_by(SaleItem.product_name)
        .order_by(desc('qty'), SaleItem.product_name)
        .limit(limit).all())
    return [{'name': r.product_name, 'qty': int(r.qty), 'revenue': _dec(r.revenue)} for r in rows]


def low_stock_products(tenant_id, limit=None):
    q = (Product.query.filter(Product.tenant_id == tenant_id, Product.is_active.is_(True),
                              Product.stock <= Product.low_stock_threshold)
         .order_by(Product.stock, Product.name))
    return q.limit(limit).all() if limit else q.all()


def low_stock_count(tenant_id):
    return (Product.query.filter(Product.tenant_id == tenant_id, Product.is_active.is_(True),
                                 Product.stock <= Product.low_stock_threshold).count())


def dashboard_metrics(tenant_id):
    month_start = local_month_start_utc()
    return {
        'today': period_totals(tenant_id, local_midnight_utc()),
        'month': period_totals(tenant_id, month_start),
        'week': last_7_days(tenant_id),
        'top': top_products(tenant_id, month_start),
        'low_stock': low_stock_products(tenant_id),
        'inventory_value': inventory_value(tenant_id),
    }


def inventory_value(tenant_id):
    cost, retail = db.session.query(
        func.coalesce(func.sum(Product.stock * Product.cost_price), 0),
        func.coalesce(func.sum(Product.stock * Product.sale_price), 0),
    ).filter(Product.tenant_id == tenant_id, Product.is_active.is_(True)).one()
    return {'cost': _dec(cost), 'retail': _dec(retail)}


def close_for_day(tenant_id, start_utc, end_utc):
    rows = (db.session.query(
        Sale.payment_method,
        func.sum(Sale.total_amount), func.sum(Sale.total_cost), func.count(Sale.id))
        .filter(Sale.tenant_id == tenant_id, Sale.voided_at.is_(None),
                Sale.created_at >= start_utc, Sale.created_at < end_utc)
        .group_by(Sale.payment_method).all())
    results = [{'method': m, 'total': _dec(t), 'profit': _dec(t) - _dec(c), 'count': int(n)}
               for m, t, c, n in rows]
    return {
        'rows': results,
        'total': sum((r['total'] for r in results), ZERO),
        'profit': sum((r['profit'] for r in results), ZERO),
        'count': sum(r['count'] for r in results),
    }
