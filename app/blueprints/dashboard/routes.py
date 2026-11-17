from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from . import dashboard_bp
from ...extensions import db, limiter
from ...models.user import User
from ...services import accounts, metrics
from ...services.tenants import check_employee_limit, delete_tenant, regenerate_code
from ...utils.decorators import login_required_with_tenant, require
from ...utils.permissions import (
    BUSINESS_SETTINGS, REPORTS_VIEW, ROLE_CLIENT, ROLE_EMPLOYEE, ROLE_OWNER, TEAM_MANAGE)
from ...utils.validation import (
    ValidationFailure, clean_text, validate_email, validate_password)


@dashboard_bp.route('/')
@login_required_with_tenant
def index():
    return render_template('dashboard/index.html')


@dashboard_bp.route('/gestion')
@login_required_with_tenant
@require(REPORTS_VIEW)
def gestion():
    data = metrics.dashboard_metrics(current_user.tenant_id)
    peak = max((d['total'] for d in data['week']), default=0)
    return render_template('dashboard/gestion.html', m=data, week_peak=peak)


# ─── CONFIGURACIÓN ──────────────────────────────────────────
@dashboard_bp.route('/configuracion')
@login_required_with_tenant
def settings():
    return render_template('dashboard/settings.html')


@dashboard_bp.route('/configuracion/actualizar', methods=['POST'])
@login_required_with_tenant
def settings_update():
    action = request.form.get('action')
    try:
        if action == 'profile':
            current_user.username = clean_text(request.form.get('username', ''), 'Nombre', max_len=80)
            db.session.commit()
            flash('Datos actualizados.', 'success')
        elif action == 'password':
            if not current_user.check_password(request.form.get('current_password', '')):
                raise ValidationFailure('La contraseña actual es incorrecta.')
            new = request.form.get('new_password', '')
            validate_password(new)
            current_user.set_password(new)
            current_user.auth_version += 1       # Cierra las demás sesiones abiertas
            db.session.commit()
            # current_user es un proxy: hay que pasar el objeto real, si no Flask-Login
            # se referencia a sí mismo y entra en recursión infinita.
            login_user(current_user._get_current_object())   # Y mantiene esta
            flash('Contraseña cambiada. Se cerraron tus otras sesiones.', 'success')
        elif action == 'business' and current_user.can(BUSINESS_SETTINGS):
            current_user.tenant.name = clean_text(
                request.form.get('business_name', ''), 'Nombre del negocio', max_len=120)
            db.session.commit()
            flash('Datos del negocio actualizados.', 'success')
        else:
            flash('Acción no permitida.', 'danger')
    except ValidationFailure as exc:
        db.session.rollback()
        flash(str(exc), 'danger')
    return redirect(url_for('dashboard.settings'))


# ─── EQUIPO ─────────────────────────────────────────────────
@dashboard_bp.route('/equipo')
@login_required_with_tenant
@require(TEAM_MANAGE)
def employees():
    members = (User.query.filter_by(tenant_id=current_user.tenant_id)
               .order_by(User.role, User.created_at).all())
    return render_template('dashboard/employees.html', members=members, tenant=current_user.tenant)


@dashboard_bp.route('/equipo/crear', methods=['POST'])
@login_required_with_tenant
@require(TEAM_MANAGE)
def employee_create():
    try:
        check_employee_limit(current_user.tenant, current_app.config['PLAN_EMPLOYEE_LIMITS'])
        username = clean_text(request.form.get('username', ''), 'Nombre', max_len=80)
        email = validate_email(request.form.get('email', ''))
        password = request.form.get('password', '')
        validate_password(password)
        if User.query.filter_by(email=email).first():
            raise ValidationFailure('Ya existe un usuario con ese email.')
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('dashboard.employees'))

    user = User(tenant_id=current_user.tenant_id, username=username, email=email,
                role=ROLE_EMPLOYEE, is_email_confirmed=True, is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'Empleado "{user.username}" creado.', 'success')
    return redirect(url_for('dashboard.employees'))


@dashboard_bp.route('/equipo/<int:user_id>/toggle', methods=['POST'])
@login_required_with_tenant
@require(TEAM_MANAGE)
def employee_toggle(user_id):
    user = User.query.filter_by(id=user_id, tenant_id=current_user.tenant_id).first_or_404()
    if user.id == current_user.id:
        flash('No podés desactivar tu propia cuenta.', 'warning')
    elif user.role == ROLE_OWNER:
        flash('No podés modificar la cuenta de un dueño.', 'danger')
    else:
        try:
            if not user.is_active and user.role == ROLE_EMPLOYEE:
                check_employee_limit(current_user.tenant, current_app.config['PLAN_EMPLOYEE_LIMITS'])
            user.is_active = not user.is_active
            user.auth_version += 1               # Echa a la persona de inmediato
            db.session.commit()
            flash(f'"{user.username}" {"activado" if user.is_active else "dado de baja"}.', 'success')
        except ValidationFailure as exc:
            flash(str(exc), 'danger')
    return redirect(url_for('dashboard.employees'))


@dashboard_bp.route('/equipo/codigo/<kind>', methods=['POST'])
@login_required_with_tenant
@require(TEAM_MANAGE)
def regenerate_invite_code(kind):
    if kind not in ('employee', 'client'):
        flash('Tipo de código inválido.', 'danger')
    else:
        try:
            regenerate_code(current_user.tenant, kind)
            flash('Código nuevo generado. El anterior ya no sirve.', 'success')
        except ValidationFailure as exc:
            flash(str(exc), 'danger')
    return redirect(url_for('dashboard.employees'))


# ─── ELIMINAR NEGOCIO ───────────────────────────────────────
@dashboard_bp.route('/configuracion/eliminar-negocio', methods=['POST'])
@login_required_with_tenant
@require(BUSINESS_SETTINGS)
@limiter.limit('5 per hour')
def delete_business():
    tenant = current_user.tenant
    # Doble confirmación: escribir el nombre exacto y la contraseña.
    if request.form.get('confirm_name', '').strip() != tenant.name:
        flash('El nombre que escribiste no coincide con el de tu negocio. No se eliminó nada.', 'danger')
        return redirect(url_for('dashboard.settings'))
    if not current_user.check_password(request.form.get('password', '')):
        flash('Contraseña incorrecta. No se eliminó nada.', 'danger')
        return redirect(url_for('dashboard.settings'))
    name = tenant.name
    delete_tenant(tenant)
    logout_user()
    flash(f'El negocio "{name}" y todos sus datos fueron eliminados. Tu cuenta sigue activa: iniciá sesión para crear otro negocio.', 'success')
    return redirect(url_for('auth.login'))


# ─── ELIMINAR MI CUENTA ─────────────────────────────────────
@dashboard_bp.route('/configuracion/eliminar-cuenta', methods=['POST'])
@login_required_with_tenant
@limiter.limit('5 per hour')
def delete_account():
    """Cada persona puede borrar su propia cuenta (empleados y clientes). El dueño primero elimina el negocio."""
    if not current_user.check_password(request.form.get('password', '')):
        flash('Contraseña incorrecta. No se eliminó nada.', 'danger')
        return redirect(url_for('dashboard.settings'))
    if request.form.get('confirm_email', '').strip().lower() != current_user.email:
        flash('El email que escribiste no coincide con el de tu cuenta. No se eliminó nada.', 'danger')
        return redirect(url_for('dashboard.settings'))
    try:
        accounts.delete_user(current_user._get_current_object())
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('dashboard.settings'))
    logout_user()
    flash('Tu cuenta fue eliminada. ¡Gracias por haber usado Fivox!', 'success')
    return redirect(url_for('public.index'))
