from datetime import datetime

from ..extensions import db


class PriceChange(db.Model):
    """
    Una fila por producto afectado en una actualización masiva de precios.
    `batch_id` agrupa las filas de una misma operación y permite revertirla.
    """
    __tablename__ = 'price_changes'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, nullable=False, index=True)
    product_id = db.Column(db.Integer, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    batch_id = db.Column(db.String(36), nullable=False, index=True)
    percent = db.Column(db.Numeric(7, 2), nullable=False)
    applies_to = db.Column(db.String(10), nullable=False)
    old_cost = db.Column(db.Numeric(10, 2), nullable=False)
    new_cost = db.Column(db.Numeric(10, 2), nullable=False)
    old_sale = db.Column(db.Numeric(10, 2), nullable=False)
    new_sale = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reverted_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        db.ForeignKeyConstraint(['tenant_id', 'product_id'], ['products.tenant_id', 'products.id'],
                                name='fk_price_changes_tenant_product', ondelete='CASCADE'),
        db.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_price_changes_tenant', ondelete='CASCADE'),
        db.Index('ix_price_changes_tenant_created', 'tenant_id', 'created_at'),
    )
