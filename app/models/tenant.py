from ..extensions import db
from datetime import datetime


class Tenant(db.Model):
    """
    Representa a cada negocio/tienda cliente (el 'inquilino').
    Un Tenant es creado automáticamente cuando un cliente se registra.
    """
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    plan = db.Column(db.String(50), default='basic')  # 'basic', 'pro', 'enterprise'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    users = db.relationship('User', backref='tenant', lazy='dynamic')
    products = db.relationship('Product', backref='tenant', lazy='dynamic')
    sales = db.relationship('Sale', backref='tenant', lazy='dynamic')

    def __repr__(self):
        return f'<Tenant {self.slug}>'
