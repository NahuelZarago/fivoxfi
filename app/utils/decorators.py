from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user


def login_required_with_tenant(f):
    """Verifica usuario autenticado y tenant activo."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Necesitás iniciar sesión.', 'warning')
            return redirect(url_for('auth.login'))
        if not current_user.is_confirmed:
            return redirect(url_for('auth.unconfirmed'))
        
        if not current_user.tenant.is_active:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Solo permite acceso a usuarios con rol 'admin'."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('No tenés permisos para acceder a esta sección.', 'danger')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def seller_or_admin_required(f):
    """Permite acceso a Admin y Vendedor (ej: POS)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ('admin', 'seller'):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
