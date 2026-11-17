from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, login_manager
from ..utils.permissions import ROLE_CLIENT, ROLE_EMPLOYEE, ROLE_LABELS, ROLE_OWNER, can


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=True, default=None)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_email_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    # Se incrementa al cambiar la contraseña: invalida sesiones y cookies "recordarme" viejas.
    # Administrador de la plataforma (vos). Solo se asigna por comando: flask --app run make-admin EMAIL
    is_superadmin = db.Column(db.Boolean, default=False, nullable=False, server_default=db.false())
    # Identificador estable de la cuenta de Google (claim 'sub'); NULL si nunca entró con Google.
    google_sub = db.Column(db.String(64), unique=True, nullable=True)
    auth_version = db.Column(db.Integer, default=0, nullable=False, server_default='0')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f'{self.id}:{self.auth_version}'

    def can(self, capability):
        return can(self.role, capability)

    @property
    def is_owner(self):
        return self.role == ROLE_OWNER

    @property
    def is_employee(self):
        return self.role == ROLE_EMPLOYEE

    @property
    def is_client(self):
        return self.role == ROLE_CLIENT

    @property
    def has_role(self):
        return self.role in ROLE_LABELS

    @property
    def role_label(self):
        if self.is_superadmin and not self.has_role:
            return 'Administrador'
        return ROLE_LABELS.get(self.role, 'Sin rol')

    def __repr__(self):
        return f'<User {self.id} role={self.role}>'


@login_manager.user_loader
def load_user(session_id):
    try:
        user_id, _, version = str(session_id).partition(':')
        user = db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None
    if user is None or str(user.auth_version) != version:
        return None
    return user
