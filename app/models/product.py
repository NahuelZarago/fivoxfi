from ..extensions import db
from datetime import datetime

LOW_STOCK_THRESHOLD = 5


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer,
        db.ForeignKey('tenants.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    sku = db.Column(db.String(100), nullable=True)
    cost_price = db.Column(db.Numeric(10, 2), nullable=False)
    sale_price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'sku', name='uq_sku_per_tenant'),
    )

    @property
    def is_low_stock(self) -> bool:
        return self.stock <= LOW_STOCK_THRESHOLD

    @property
    def profit_margin(self):
        return float(self.sale_price) - float(self.cost_price)

    def to_dict(self):
        """Serializa el producto para respuestas JSON (usado en el POS)."""
        return {
            'id': self.id,
            'name': self.name,
            'sku': self.sku or '',
            'sale_price': float(self.sale_price),
            'stock': self.stock,
            'is_low_stock': self.is_low_stock,
        }

    def __repr__(self):
        return f'<Product {self.name} | Stock: {self.stock}>'
