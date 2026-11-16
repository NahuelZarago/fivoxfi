"""Utilidades de los tests con base de datos (requieren las dependencias completas)."""
from app import create_app
from app.extensions import db
from app.models import Product, Tenant, User

PASSWORD = 'Clave1234'
