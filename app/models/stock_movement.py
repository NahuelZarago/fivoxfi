from datetime import datetime

from ..extensions import db

# Motivos. quantity_change es SIEMPRE con signo: + entra, - sale.
REASON_PURCHASE = 'purchase'        # Compra / reposición (+)
REASON_SALE = 'sale'                # Venta (-)
REASON_VOID = 'sale_void'           # Anulación de venta (+)
REASON_LOSS = 'loss'                # Merma / rotura / vencimiento (-)
REASON_ADJUSTMENT = 'adjustment'    # Ajuste de inventario (+/-)
REASON_INITIAL = 'initial'          # Stock inicial al crear el producto (+)

REASON_LABELS = {
    REASON_PURCHASE: 'Compra / reposición',
    REASON_SALE: 'Venta',
    REASON_VOID: 'Venta anulada',
    REASON_LOSS: 'Merma / pérdida',
    REASON_ADJUSTMENT: 'Ajuste de inventario',
    REASON_INITIAL: 'Stock inicial',
}


class StockMovement(db.Model):
    """Libro de movimientos inmutable: nunca se edita ni se borra."""
    __tablename__ = 'stock_movements'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    product_id = db.Column(db.Integer, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id', ondelete='SET NULL'), nullable=True, index=True)
    reason = db.Column(db.String(20), nullable=False)
    quantity_change = db.Column(db.Integer, nullable=False)
    stock_after = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        # FK compuesta: un movimiento no puede apuntar a un producto de OTRO negocio.
        db.ForeignKeyConstraint(['tenant_id', 'product_id'], ['products.tenant_id', 'products.id'],
                                name='fk_movements_tenant_product', ondelete='CASCADE'),
        db.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_movements_tenant', ondelete='CASCADE'),
        db.CheckConstraint('quantity_change <> 0', name='ck_movements_nonzero'),
        db.CheckConstraint('stock_after >= 0', name='ck_movements_stock_after_nonneg'),
        db.Index('ix_movements_tenant_created', 'tenant_id', 'created_at'),
    )

    @property
    def reason_label(self):
        return REASON_LABELS.get(self.reason, self.reason)
