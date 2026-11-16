"""Utilidades de los tests con base de datos (requieren las dependencias completas)."""
from app.extensions import db
from app.models import Product, Tenant, User

PASSWORD = 'Clave1234'


def make_tenant(name='Kiosco', slug=None):
    t = Tenant(name=name, slug=slug or name.lower())
    db.session.add(t)
    db.session.commit()
    return t


def make_user(tenant, role, email=None, active=True):
    email = email or f'{role}{User.query.count()}@t.com'
    u = User(tenant_id=tenant.id if tenant else None, email=email, username=role.title(),
             role=role, is_email_confirmed=True, is_active=active)
    u.set_password(PASSWORD)
    db.session.add(u)
    db.session.commit()
    return u


def make_product(tenant, name='Yerba', cost='100.00', price='150.00', stock=10, **kw):
    p = Product(tenant_id=tenant.id, name=name, cost_price=cost, sale_price=price, stock=stock, **kw)
    db.session.add(p)
    db.session.commit()
    return p


def login(client, user, password=PASSWORD, **kw):
    return client.post('/auth/login', data={'email': user.email, 'password': password}, **kw)