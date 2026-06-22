from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user


def login_required_with_tenant(f):
    """
    Verifica: autenticado + email confirmado + rol elegido + tenant asignado.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Iniciá sesión para continuar.', 'warning')
            return redirect(url_for('auth.login'))
        if not current_user.is_email_confirmed:
            return redirect(url_for('auth.pending_verification'))
        if not current_user.has_role or not current_user.tenant_id:
            return redirect(url_for('auth.choose_role'))
        if not current_user.is_active:
            flash('Tu cuenta fue desactivada. Contactá al administrador.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.tenant.is_active:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def owner_required(f):
    """Solo owners (dueños) pueden acceder."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_owner:
            flash('Solo el dueño del negocio puede acceder a esta sección.', 'danger')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def seller_or_owner_required(f):
    """Owners y sellers pueden acceder (ej: POS)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ('owner', 'seller'):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# Alias para compatibilidad con código anterior
admin_required = owner_required
