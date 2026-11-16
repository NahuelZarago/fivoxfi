from datetime import datetime
from decimal import Decimal

from ..extensions import db
from ..models.product import Product
from ..models.sale import Sale, SaleItem
from ..models.stock_movement import REASON_SALE, REASON_VOID
from ..utils.validation import MAX_QUANTITY, ValidationFailure
from .inventory import apply_movement, lock_products

PAYMENT_METHODS = {
    'cash': 'Efectivo',
    'card': 'Tarjeta',
    'transfer': 'Transferencia',
    'mercadopago': 'Mercado Pago',
}
MAX_ITEMS_PER_SALE = 100


def create_sale(tenant_id, seller_id, raw_items, payment_method='cash', notes=None):
    """
    raw_items: [{'product_id': int, 'quantity': int}, ...]  (datos del cliente: no se confía en nada)
    Los precios SIEMPRE salen de la base. Devuelve la Sale (hay commit).
    """
    if payment_method not in PAYMENT_METHODS:
        raise ValidationFailure('Medio de pago inválido.')
    if not isinstance(raw_items, list) or not raw_items:
        raise ValidationFailure('No se recibieron productos.')
    if len(raw_items) > MAX_ITEMS_PER_SALE:
        raise ValidationFailure(f'Máximo {MAX_ITEMS_PER_SALE} renglones por venta.')

    # Consolidar renglones repetidos del mismo producto.
    wanted = {}
    for entry in raw_items:
        if not isinstance(entry, dict):
            raise ValidationFailure('Formato de producto inválido.')
        pid, qty = entry.get('product_id'), entry.get('quantity')
        if isinstance(pid, bool) or isinstance(qty, bool) or not isinstance(pid, int) or not isinstance(qty, int):
            raise ValidationFailure('Producto o cantidad inválidos.')
        if qty <= 0 or qty > MAX_QUANTITY:
            raise ValidationFailure('La cantidad debe ser mayor a cero.')
        wanted[pid] = wanted.get(pid, 0) + qty

    try:
        products = lock_products(tenant_id, wanted.keys())
        missing = set(wanted) - set(products)
        if missing:
            raise ValidationFailure('Alguno de los productos ya no está disponible. Actualizá la pantalla.')

        sale = Sale(tenant_id=tenant_id, seller_id=seller_id, payment_method=payment_method,
                    notes=(notes or None), total_amount=Decimal('0'), total_cost=Decimal('0'))
        total, cost = Decimal('0'), Decimal('0')
        for pid in sorted(wanted):
            product, qty = products[pid], wanted[pid]
            total += product.sale_price * qty
            cost += product.cost_price * qty
            sale.items.append(SaleItem(
                product_id=product.id, product_name=product.name, quantity=qty,
                unit_sale_price=product.sale_price, unit_cost_price=product.cost_price))
        sale.total_amount, sale.total_cost = total, cost
        db.session.add(sale)
        db.session.flush()  # Necesitamos sale.id para los movimientos

        for pid in sorted(wanted):
            apply_movement(products[pid], -wanted[pid], REASON_SALE, user_id=seller_id, sale_id=sale.id)
        db.session.commit()
        return sale
    except Exception:
        db.session.rollback()
        raise


def void_sale(tenant_id, sale_id, user_id, reason=None):
    """Anula una venta: devuelve el stock y deja de contar en métricas."""
    try:
        sale = (Sale.query.filter_by(id=sale_id, tenant_id=tenant_id)
                .with_for_update().first())
        if sale is None:
            raise ValidationFailure('Venta no encontrada.')
        if sale.is_voided:
            raise ValidationFailure('Esa venta ya estaba anulada.')

        ids = [i.product_id for i in sale.items if i.product_id]
        # Para devolver stock también sirven productos hoy inactivos.
        products = {p.id: p for p in (
            Product.query.filter(Product.tenant_id == tenant_id, Product.id.in_(sorted(set(ids))))
            .order_by(Product.id).with_for_update().all())} if ids else {}
        for item in sale.items:
            product = products.get(item.product_id)
            if product is not None:
                apply_movement(product, item.quantity, REASON_VOID, user_id=user_id, sale_id=sale.id,
                               note=f'Anulación venta #{sale.id}')
        sale.voided_at = datetime.utcnow()
        sale.voided_by_id = user_id
        sale.void_reason = (reason or None)
        db.session.commit()
        return sale
    except Exception:
        db.session.rollback()
        raise
