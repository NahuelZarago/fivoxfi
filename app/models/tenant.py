import random
import string
from ..extensions import db
from datetime import datetime


def generate_employee_code():
    chars = string.ascii_uppercase + string.digits
    return 'FX-' + ''.join(random.choices(chars, k=6))


class Tenant(db.Model):
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    plan = db.Column(db.String(50), default='basic')
    employee_code = db.Column(db.String(20), unique=True, nullable=False, default=generate_employee_code)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship('User', backref='tenant', lazy='dynamic')
    products = db.relationship('Product', backref='tenant', lazy='dynamic')
    sales = db.relationship('Sale', backref='tenant', lazy='dynamic')

    def __repr__(self):
        return f'<Tenant {self.slug} code={self.employee_code}>'
