"""Borrado de cuentas y estadísticas de la plataforma."""
from datetime import timedelta

from ..extensions import db
from ..models.product import Product
from ..models.sale import Sale
from ..models.tenant import Tenant
from ..models.user import User
from ..utils.text import escape_like
from ..utils.timeutils import utcnow
from ..utils.validation import ValidationFailure


def delete_user(user):
    """
    Borra una cuenta. Las ventas y movimientos que hizo se conservan (quedan sin autor).
    No se puede borrar a un administrador ni a un dueño con negocio: primero hay que eliminar el negocio.
    """
    if user.is_superadmin:
        raise ValidationFailure('Un administrador no se puede borrar: primero quitale el permiso con el comando remove-admin.')
    if user.tenant_id and user.is_owner:
        raise ValidationFailure('Esta persona es dueña de un negocio. Eliminá primero el negocio y después la cuenta.')
    try:
        # Borrado en bloque: evita que el ORM intente tocar relaciones (ventas, movimientos).
        User.query.filter_by(id=user.id).delete(synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def platform_stats():
    now = utcnow()
    week = now - timedelta(days=7)
    count = lambda q: q.scalar() or 0  # noqa: E731
    return {
        'tenants': count(db.session.query(db.func.count(Tenant.id))),
        'tenants_active': count(db.session.query(db.func.count(Tenant.id)).filter(Tenant.is_active.is_(True))),
        'users': count(db.session.query(db.func.count(User.id))),
        'unverified': count(db.session.query(db.func.count(User.id)).filter(User.is_email_confirmed.is_(False))),
        'no_business': count(db.session.query(db.func.count(User.id)).filter(
            User.tenant_id.is_(None), User.is_superadmin.is_(False))),
        'new_users_week': count(db.session.query(db.func.count(User.id)).filter(User.created_at >= week)),
        'new_tenants_week': count(db.session.query(db.func.count(Tenant.id)).filter(Tenant.created_at >= week)),
        'products': count(db.session.query(db.func.count(Product.id))),
        'sales': count(db.session.query(db.func.count(Sale.id)).filter(Sale.voided_at.is_(None))),
    }


def tenant_rows(search, page, per_page=25):
    users_n = (db.session.query(User.tenant_id.label('tid'), db.func.count(User.id).label('n'))
               .group_by(User.tenant_id).subquery())
    prods_n = (db.session.query(Product.tenant_id.label('tid'), db.func.count(Product.id).label('n'))
               .group_by(Product.tenant_id).subquery())
    sales_n = (db.session.query(Sale.tenant_id.label('tid'), db.func.count(Sale.id).label('n'))
               .group_by(Sale.tenant_id).subquery())
    owner = (db.session.query(User.tenant_id.label('tid'), db.func.min(User.email).label('email'))
             .filter(User.role == 'owner').group_by(User.tenant_id).subquery())
    q = (db.session.query(Tenant, db.func.coalesce(users_n.c.n, 0), db.func.coalesce(prods_n.c.n, 0),
                          db.func.coalesce(sales_n.c.n, 0), owner.c.email)
         .outerjoin(users_n, users_n.c.tid == Tenant.id).outerjoin(prods_n, prods_n.c.tid == Tenant.id)
         .outerjoin(sales_n, sales_n.c.tid == Tenant.id).outerjoin(owner, owner.c.tid == Tenant.id))
    if search:
        like = f'%{escape_like(search)}%'
        q = q.filter(db.or_(Tenant.name.ilike(like, escape='\\'), owner.c.email.ilike(like, escape='\\')))
    return q.order_by(Tenant.created_at.desc(), Tenant.id.desc()).paginate(page=page, per_page=per_page, error_out=False)


def user_rows(search, page, per_page=25):
    q = User.query
    if search:
        like = f'%{escape_like(search)}%'
        q = q.filter(db.or_(User.email.ilike(like, escape='\\'), User.username.ilike(like, escape='\\')))
    return q.order_by(User.created_at.desc(), User.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
