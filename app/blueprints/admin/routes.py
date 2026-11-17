from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from . import admin_bp
from ...extensions import db, limiter
from ...models.tenant import Tenant
from ...models.user import User
from ...services import accounts
from ...services.tenants import delete_tenant
from ...utils.decorators import superadmin_required
from ...utils.validation import ValidationFailure


def _back(endpoint):
    """Vuelve a la misma lista (misma búsqueda y página) tras una acción."""
    return redirect(url_for(endpoint, q=request.form.get('q', ''), page=request.form.get('page', 1, type=int)))


def _password_ok():
    """Las acciones destructivas piden de nuevo la contraseña del administrador."""
    return current_user.check_password(request.form.get('admin_password', ''))


@admin_bp.route('/')
@superadmin_required
def index():
    return render_template('admin/index.html', s=accounts.platform_stats())


# ─── NEGOCIOS ───────────────────────────────────────────────
@admin_bp.route('/negocios')
@superadmin_required
def tenants():
    q = request.args.get('q', '').strip()[:100]
    page = request.args.get('page', 1, type=int)
    return render_template('admin/tenants.html', rows=accounts.tenant_rows(q, page), q=q,
                           plans=list(current_app.config['PLAN_EMPLOYEE_LIMITS']))


@admin_bp.route('/negocios/<int:tenant_id>/estado', methods=['POST'])
@superadmin_required
def tenant_toggle(tenant_id):
    tenant = db.get_or_404(Tenant, tenant_id)
    tenant.is_active = not tenant.is_active
    db.session.commit()
    flash(f'Negocio "{tenant.name}" {"activado" if tenant.is_active else "suspendido"}.', 'success')
    return _back('admin.tenants')


@admin_bp.route('/negocios/<int:tenant_id>/plan', methods=['POST'])
@superadmin_required
def tenant_plan(tenant_id):
    tenant = db.get_or_404(Tenant, tenant_id)
    plan = request.form.get('plan', '')
    if plan not in current_app.config['PLAN_EMPLOYEE_LIMITS']:
        flash('Plan inválido.', 'danger')
    else:
        tenant.plan = plan
        db.session.commit()
        flash(f'Plan de "{tenant.name}" cambiado a {plan}.', 'success')
    return _back('admin.tenants')


@admin_bp.route('/negocios/<int:tenant_id>/eliminar', methods=['POST'])
@superadmin_required
@limiter.limit('20 per hour')
def tenant_delete(tenant_id):
    tenant = db.get_or_404(Tenant, tenant_id)
    if request.form.get('confirm_name', '').strip() != tenant.name:
        flash('El nombre no coincide. No se eliminó nada.', 'danger')
    elif not _password_ok():
        flash('Tu contraseña de administrador es incorrecta. No se eliminó nada.', 'danger')
    else:
        name = tenant.name
        delete_tenant(tenant)
        flash(f'Negocio "{name}" eliminado con todos sus datos.', 'success')
    return _back('admin.tenants')


# ─── USUARIOS ───────────────────────────────────────────────
@admin_bp.route('/usuarios')
@superadmin_required
def users():
    q = request.args.get('q', '').strip()[:100]
    page = request.args.get('page', 1, type=int)
    return render_template('admin/users.html', rows=accounts.user_rows(q, page), q=q)


def _target_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        raise ValidationFailure('No podés hacer eso con tu propia cuenta desde el panel.')
    if user.is_superadmin:
        raise ValidationFailure('No se puede modificar a otro administrador desde el panel.')
    return user


@admin_bp.route('/usuarios/<int:user_id>/estado', methods=['POST'])
@superadmin_required
def user_toggle(user_id):
    try:
        user = _target_user(user_id)
        user.is_active = not user.is_active
        user.auth_version += 1               # Echa a la persona de inmediato
        db.session.commit()
        flash(f'Cuenta {user.email} {"activada" if user.is_active else "desactivada"}.', 'success')
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
    return _back('admin.users')


@admin_bp.route('/usuarios/<int:user_id>/verificar', methods=['POST'])
@superadmin_required
def user_verify(user_id):
    """Marca el email como verificado a mano (útil si el correo no llega)."""
    user = db.get_or_404(User, user_id)
    user.is_email_confirmed = True
    db.session.commit()
    flash(f'Email de {user.email} marcado como verificado.', 'success')
    return _back('admin.users')


@admin_bp.route('/usuarios/<int:user_id>/eliminar', methods=['POST'])
@superadmin_required
@limiter.limit('30 per hour')
def user_delete(user_id):
    try:
        user = _target_user(user_id)
        if not _password_ok():
            raise ValidationFailure('Tu contraseña de administrador es incorrecta. No se eliminó nada.')
        email = user.email
        accounts.delete_user(user)
        flash(f'Cuenta {email} eliminada.', 'success')
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
    return _back('admin.users')
