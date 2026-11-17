"""Datasets exportables. Cada uno devuelve (nombre de archivo base, columnas, filas)."""
from sqlalchemy import func

from ..extensions import db
from ..models.product import Product
from ..models.sale import Sale, SaleItem
from ..models.stock_movement import REASON_LABELS, StockMovement
from ..models.user import User
from ..utils.timeutils import local_day_bounds_utc, to_local
from ..utils.xlsx import DATETIME, INT, MONEY, TEXT

MAX_EXPORT_ROWS = 50_000


def _local(dt):
    value = to_local(dt)
    return value.replace(tzinfo=None) if value else None


def products_dataset(tenant_id, include_costs):
    cols = [('Nombre', TEXT, 34), ('SKU', TEXT, 16), ('Stock', INT, 9), ('Stock mínimo', INT, 13),
            ('Precio de venta', MONEY, 16)]
    if include_costs:
        cols[4:4] = [('Precio de compra', MONEY, 16)]
        cols.append(('Margen unitario', MONEY, 16))
        cols.append(('Valor en stock (costo)', MONEY, 22))
    cols.append(('Activo', TEXT, 9))
    rows = []
    q = Product.query.filter_by(tenant_id=tenant_id).order_by(Product.name).limit(MAX_EXPORT_ROWS)
    for p in q:
        row = [p.name, p.sku or '', p.stock, p.low_stock_threshold]
        if include_costs:
            row += [p.cost_price, p.sale_price, p.sale_price - p.cost_price, p.cost_price * p.stock]
        else:
            row += [p.sale_price]
        row.append('Sí' if p.is_active else 'No')
        rows.append(row)
    return 'productos', cols, rows


def sales_dataset(tenant_id, start_day, end_day, include_voided):
    """Una fila por ítem vendido, entre dos fechas locales (inclusive)."""
    start, _ = local_day_bounds_utc(start_day)
    _, end = local_day_bounds_utc(end_day)
    cols = [('Venta N°', INT, 9), ('Fecha', DATETIME, 18), ('Producto', TEXT, 34), ('Cantidad', INT, 10),
            ('Precio unitario', MONEY, 16), ('Costo unitario', MONEY, 16), ('Subtotal', MONEY, 14),
            ('Ganancia', MONEY, 14), ('Medio de pago', TEXT, 16), ('Vendedor', TEXT, 20), ('Estado', TEXT, 12)]
    q = (db.session.query(Sale, SaleItem, User.username)
         .join(SaleItem, SaleItem.sale_id == Sale.id)
         .outerjoin(User, User.id == Sale.seller_id)
         .filter(Sale.tenant_id == tenant_id, Sale.created_at >= start, Sale.created_at < end))
    if not include_voided:
        q = q.filter(Sale.voided_at.is_(None))
    q = q.order_by(Sale.created_at, Sale.id, SaleItem.id).limit(MAX_EXPORT_ROWS)
    rows = []
    for sale, item, seller in q:
        sub = item.unit_sale_price * item.quantity
        rows.append([sale.id, _local(sale.created_at), item.product_name, item.quantity,
                     item.unit_sale_price, item.unit_cost_price, sub,
                     sub - item.unit_cost_price * item.quantity, sale.payment_method,
                     seller or '', 'ANULADA' if sale.voided_at else 'OK'])
    return 'ventas', cols, rows


def movements_dataset(tenant_id, start_day, end_day):
    start, _ = local_day_bounds_utc(start_day)
    _, end = local_day_bounds_utc(end_day)
    cols = [('Fecha', DATETIME, 18), ('Producto', TEXT, 34), ('Motivo', TEXT, 22), ('Cambio', INT, 9),
            ('Stock resultante', INT, 16), ('Usuario', TEXT, 20), ('Nota', TEXT, 30)]
    names = dict(db.session.query(Product.id, Product.name).filter_by(tenant_id=tenant_id).all())
    q = (db.session.query(StockMovement, User.username)
         .outerjoin(User, User.id == StockMovement.user_id)
         .filter(StockMovement.tenant_id == tenant_id, StockMovement.created_at >= start,
                 StockMovement.created_at < end)
         .order_by(StockMovement.created_at, StockMovement.id).limit(MAX_EXPORT_ROWS))
    rows = [[_local(m.created_at), names.get(m.product_id, f'#{m.product_id}'),
             REASON_LABELS.get(m.reason, m.reason), m.quantity_change, m.stock_after,
             user or '', m.note or ''] for m, user in q]
    return 'movimientos', cols, rows
