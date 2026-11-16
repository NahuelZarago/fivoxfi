"""Operaciones de stock. Toda variación de stock pasa por acá y deja un movimiento."""
from ..extensions import db
from ..models.product import Product
from ..models.stock_movement import (
    REASON_ADJUSTMENT, REASON_LOSS, REASON_PURCHASE, StockMovement)
from ..utils.validation import ValidationFailure


def lock_products(tenant_id, product_ids):
    """
    Bloquea las filas (SELECT ... FOR UPDATE) en orden por id, para que dos ventas
    simultáneas no pisen el stock ni se bloqueen entre sí (siempre mismo orden).
    Devuelve {id: Product}. Solo productos activos del tenant.
    """
    ids = sorted(set(product_ids))
    if not ids:
        return {}
    rows = (Product.query
            .filter(Product.tenant_id == tenant_id, Product.id.in_(ids), Product.is_active.is_(True))
            .order_by(Product.id)
            .with_for_update()
            .all())
    return {p.id: p for p in rows}


def apply_movement(product, change, reason, user_id=None, sale_id=None, note=None):
    """
    Aplica `change` (con signo) a un producto YA bloqueado y registra el movimiento.
    No hace commit: lo hace quien llama, para que todo sea una sola transacción.
    """
    if change == 0:
        raise ValidationFailure('La cantidad no puede ser cero.')
    new_stock = product.stock + change
    if new_stock < 0:
        raise ValidationFailure(
            f'Stock insuficiente para "{product.name}". Disponible: {product.stock}.')
    product.stock = new_stock
    movement = StockMovement(
        tenant_id=product.tenant_id, product_id=product.id, user_id=user_id, sale_id=sale_id,
        reason=reason, quantity_change=change, stock_after=new_stock, note=(note or None))
    db.session.add(movement)
    return movement


def register_manual_movement(tenant_id, product_id, kind, quantity, user_id, note=None):
    """
    kind: 'entry' (compra/reposición), 'loss' (merma) o 'adjust_set' (fijar stock contado).
    Para 'adjust_set', `quantity` es el stock real contado.
    """
    products = lock_products(tenant_id, [product_id])
    product = products.get(product_id)
    if product is None:
        raise ValidationFailure('Producto no encontrado.')
    if kind == 'entry':
        if quantity <= 0:
            raise ValidationFailure('La cantidad debe ser mayor a cero.')
        return apply_movement(product, quantity, REASON_PURCHASE, user_id=user_id, note=note)
    if kind == 'loss':
        if quantity <= 0:
            raise ValidationFailure('La cantidad debe ser mayor a cero.')
        return apply_movement(product, -quantity, REASON_LOSS, user_id=user_id, note=note)
    if kind == 'adjust_set':
        if quantity < 0:
            raise ValidationFailure('El stock contado no puede ser negativo.')
        delta = quantity - product.stock
        if delta == 0:
            raise ValidationFailure('El stock contado coincide con el actual: no hay nada que ajustar.')
        return apply_movement(product, delta, REASON_ADJUSTMENT, user_id=user_id, note=note)
    raise ValidationFailure('Tipo de movimiento inválido.')
