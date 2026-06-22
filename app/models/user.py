from ..extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class User(UserMixin, db.Model):
    """
    Un User puede ser:
    - 'owner': dueño de un negocio (tiene tenant_id propio, acceso total)
    - 'seller': empleado (tenant_id asignado al unirse con código)
    
    Los owners se registran en /auth/registro → verifican email → eligen rol owner.
    Los sellers se registran → verifican email → eligen rol seller → ingresan código.
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)

    # tenant_id es nullable: se asigna cuando el usuario elige su rol post-verificación
    tenant_id = db.Column(
        db.Integer,
        db.ForeignKey('tenants.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )

    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    # 'owner' = dueño/admin del negocio
    # 'seller' = empleado, solo accede al POS
    # None = todavía no eligió rol (recién verificó email)
    role = db.Column(db.String(20), nullable=True, default=None)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_email_confirmed = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_owner(self) -> bool:
        return self.role == 'owner'

    @property
    def is_seller(self) -> bool:
        return self.role == 'seller'

    @property
    def is_admin(self) -> bool:
        """Alias de is_owner para compatibilidad con decoradores y templates."""
        return self.role == 'owner'

    @property
    def has_role(self) -> bool:
        """True si ya eligió su rol (owner o seller)."""
        return self.role in ('owner', 'seller')

    def __repr__(self):
        return f'<User {self.email} | role={self.role} | tenant={self.tenant_id}>'


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))
