from datetime import datetime

from ..extensions import db
from ..utils.codes import generate_client_code, generate_employee_code


class Tenant(db.Model):
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    plan = db.Column(db.String(50), default='basic', nullable=False)
    employee_code = db.Column(db.String(20), unique=True, nullable=False, default=generate_employee_code)
    client_code = db.Column(db.String(20), unique=True, nullable=False, default=generate_client_code)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship('User', backref='tenant', lazy='dynamic')
    products = db.relationship('Product', backref='tenant', lazy='dynamic')
    sales = db.relationship('Sale', backref='tenant', lazy='dynamic')

    def __repr__(self):
        return f'<Tenant {self.slug}>'
