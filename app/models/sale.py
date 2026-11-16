from datetime import datetime
from decimal import Decimal

from ..extensions import db


class Sale(db.Model):
    __tablename__ = 'sales'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    total_cost = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False, default='cash')
    notes = db.Column(db.Text, nullable=True)
    # Anulación: la venta se conserva (auditoría) pero deja de contar y devuelve el stock.
    voided_at = db.Column(db.DateTime, nullable=True)
    voided_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    void_reason = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    items = db.relationship('SaleItem', backref='sale', lazy='selectin', cascade='all, delete-orphan')
    seller = db.relationship('User', backref='sales', foreign_keys=[seller_id])
    voided_by = db.relationship('User', foreign_keys=[voided_by_id])

    __table_args__ = (
        db.Index('ix_sales_tenant_created', 'tenant_id', 'created_at'),
    )

    @property
    def is_voided(self):
        return self.voided_at is not None

    @property
    def net_profit(self):
        return Decimal(self.total_amount) - Decimal(self.total_cost)


class SaleItem(db.Model):
    __tablename__ = 'sale_items'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True, index=True)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_sale_price = db.Column(db.Numeric(10, 2), nullable=False)
    unit_cost_price = db.Column(db.Numeric(10, 2), nullable=False)

    product = db.relationship('Product', backref='sale_items')

    __table_args__ = (db.CheckConstraint('quantity > 0', name='ck_sale_items_qty_pos'),)

    @property
    def subtotal(self):
        return Decimal(self.unit_sale_price) * self.quantity
