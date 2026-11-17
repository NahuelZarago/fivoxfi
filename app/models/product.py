from datetime import datetime

from ..extensions import db

DEFAULT_LOW_STOCK_THRESHOLD = 5


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    sku = db.Column(db.String(100), nullable=True)
    cost_price = db.Column(db.Numeric(10, 2), nullable=False)
    sale_price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=DEFAULT_LOW_STOCK_THRESHOLD,
                                    server_default=str(DEFAULT_LOW_STOCK_THRESHOLD))
    category_id = db.Column(db.Integer, nullable=True, index=True)
    supplier_id = db.Column(db.Integer, nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Solo lectura (se cargan con selectinload donde se muestran; un JOIN rompería los FOR UPDATE):
    #  category_id / supplier_id se asignan a mano (la FK compuesta incluye tenant_id).
    category = db.relationship('Category', viewonly=True)
    supplier = db.relationship('Supplier', viewonly=True)

    __table_args__ = (
        db.ForeignKeyConstraint(['tenant_id', 'category_id'], ['categories.tenant_id', 'categories.id'],
                                name='fk_products_tenant_category'),
        db.ForeignKeyConstraint(['tenant_id', 'supplier_id'], ['suppliers.tenant_id', 'suppliers.id'],
                                name='fk_products_tenant_supplier'),
        db.UniqueConstraint('tenant_id', 'sku', name='uq_sku_per_tenant'),
        # Necesario para la FK compuesta de stock_movements (aislamiento por tenant en la base).
        db.UniqueConstraint('tenant_id', 'id', name='uq_products_tenant_id_id'),
        db.CheckConstraint('stock >= 0', name='ck_products_stock_nonneg'),
        db.CheckConstraint('cost_price >= 0 AND sale_price >= 0', name='ck_products_prices_nonneg'),
    )

    @property
    def is_out_of_stock(self):
        return self.stock <= 0

    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold

    @property
    def unit_margin(self):
        return self.sale_price - self.cost_price

    def __repr__(self):
        return f'<Product {self.id} {self.name}>'
