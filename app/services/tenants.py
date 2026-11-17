from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.tenant import Tenant
from ..models.user import User
from ..utils.codes import generate_client_code, generate_employee_code, normalize_code
from ..utils.permissions import ROLE_CLIENT, ROLE_EMPLOYEE, ROLE_OWNER
from ..utils.text import slugify
from ..utils.validation import ValidationFailure


def create_tenant_for_owner(user, business_name, attempts=8):
    """
    Crea el negocio y convierte al usuario en dueño. Los códigos y el slug se
    generan al azar/derivados y la unicidad la garantiza la base: si hay choque
    (IntegrityError) se reintenta con otros valores, sin carreras.
    """
    base = slugify(business_name)
    last_error = None
    for n in range(attempts):
        slug = base if n == 0 else f'{base[:50]}-{n + 1}'
        tenant = Tenant(name=business_name, slug=slug,
                        employee_code=generate_employee_code(), client_code=generate_client_code())
        db.session.add(tenant)
        try:
            db.session.flush()
        except IntegrityError as exc:
            db.session.rollback()          # Rollback completo: el usuario se vuelve a cargar solo
            last_error = exc
            user = db.session.get(User, user.id)
            continue
        user.tenant_id = tenant.id
        user.role = ROLE_OWNER
        db.session.commit()
        return tenant
    raise ValidationFailure('No se pudo crear el negocio. Intentá de nuevo.') from last_error


def join_with_code(user, raw_code, employee_limits=None):
    """El prefijo del código decide el rol: FX- empleado, FC- cliente."""
    code = normalize_code(raw_code)
    if code is None:
        raise ValidationFailure('Código inválido. Revisá que esté bien escrito.')
    if code.startswith('FX-'):
        tenant = Tenant.query.filter_by(employee_code=code, is_active=True).first()
        role = ROLE_EMPLOYEE
    else:
        tenant = Tenant.query.filter_by(client_code=code, is_active=True).first()
        role = ROLE_CLIENT
    if tenant is None:
        raise ValidationFailure('Código incorrecto o negocio inactivo.')
    if role == ROLE_EMPLOYEE:
        check_employee_limit(tenant, employee_limits)
    user.tenant_id = tenant.id
    user.role = role
    db.session.commit()
    return tenant


def check_employee_limit(tenant, limits):
    limit = (limits or {}).get(tenant.plan)
    if limit is None:
        return
    active = User.query.filter_by(tenant_id=tenant.id, role=ROLE_EMPLOYEE, is_active=True).count()
    if active >= limit:
        raise ValidationFailure(
            f'El plan actual permite hasta {limit} empleados activos. Pedile al dueño que dé de baja a alguno o mejore el plan.')


def regenerate_code(tenant, kind):
    for _ in range(8):
        try:
            if kind == 'employee':
                tenant.employee_code = generate_employee_code()
            else:
                tenant.client_code = generate_client_code()
            db.session.commit()
            return
        except IntegrityError:
            db.session.rollback()
    raise ValidationFailure('No se pudo generar un código nuevo. Intentá de nuevo.')


def delete_tenant(tenant):
    """
    Elimina el negocio y TODOS sus datos (productos, ventas, movimientos). Irreversible.
    Las personas del equipo (empleados, clientes y el propio dueño) NO se borran: quedan sin
    negocio, con la sesión cerrada, y pueden unirse a otro o registrar uno nuevo.
    Todo en una sola transacción: o se borra todo o no se borra nada.
    """
    from ..models.product import Product
    from ..models.cash_session import CashSession
    from ..models.catalog import Category, Supplier
    from ..models.price_change import PriceChange
    from ..models.sale import Sale, SaleItem
    from ..models.stock_movement import StockMovement

    tid = tenant.id
    try:
        sale_ids = db.session.query(Sale.id).filter(Sale.tenant_id == tid)
        StockMovement.query.filter_by(tenant_id=tid).delete(synchronize_session=False)
        PriceChange.query.filter_by(tenant_id=tid).delete(synchronize_session=False)
        CashSession.query.filter_by(tenant_id=tid).delete(synchronize_session=False)
        SaleItem.query.filter(SaleItem.sale_id.in_(sale_ids)).delete(synchronize_session=False)
        Sale.query.filter_by(tenant_id=tid).delete(synchronize_session=False)
        Product.query.filter_by(tenant_id=tid).delete(synchronize_session=False)
        Category.query.filter_by(tenant_id=tid).delete(synchronize_session=False)
        Supplier.query.filter_by(tenant_id=tid).delete(synchronize_session=False)
        # auth_version + 1 cierra las sesiones abiertas de todo el equipo
        User.query.filter_by(tenant_id=tid).update(
            {User.tenant_id: None, User.role: None, User.auth_version: User.auth_version + 1},
            synchronize_session=False)
        Tenant.query.filter_by(id=tid).delete(synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
