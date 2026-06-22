from ..extensions import db
from datetime import datetime


class Sale(db.Model):
    __tablename__ = 'sales'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    total_cost = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False, default='cash')
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    items = db.relationship('SaleItem', backref='sale', lazy='joined', cascade='all, delete-orphan')
    seller = db.relationship('User', backref='sales', foreign_keys=[seller_id])

    @property
    def net_profit(self):
        return float(self.total_amount) - float(self.total_cost)


class SaleItem(db.Model):
    __tablename__ = 'sale_items'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True)
    product_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_sale_price = db.Column(db.Numeric(10, 2), nullable=False)
    unit_cost_price = db.Column(db.Numeric(10, 2), nullable=False)

    product = db.relationship('Product', backref='sale_items')

    @property
    def subtotal(self):
        return float(self.unit_sale_price) * self.quantity

    @property
    def item_profit(self):
        return (float(self.unit_sale_price) - float(self.unit_cost_price)) * self.quantity
