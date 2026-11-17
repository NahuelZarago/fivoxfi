from functools import wraps

from flask import abort, flash, jsonify, redirect, request, url_for
from flask_login import current_user

from .permissions import can


def _wants_json():
    return request.path.startswith('/app/pos/api') or request.is_json


def login_required_with_tenant(f):
    """Sesión válida + email verificado + rol + negocio activo."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            if _wants_json():
                return jsonify({'error': 'Sesión expirada. Volvé a iniciar sesión.'}), 401
            flash('Iniciá sesión para continuar.', 'warning')
            return redirect(url_for('auth.login', next=request.full_path.rstrip('?')))
        if not current_user.is_active:
            # Antes esto causaba un bucle de redirecciones login<->dashboard.
            from flask_login import logout_user
            logout_user()
            flash('Tu cuenta fue desactivada. Contactá al dueño del negocio.', 'danger')
            return redirect(url_for('auth.login'))
        if not current_user.is_email_confirmed:
            return redirect(url_for('auth.pending_verification'))
        if not current_user.has_role or not current_user.tenant_id:
            return redirect(url_for('auth.choose_role'))
        if not current_user.tenant.is_active:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def require(capability):
    """Exige una capacidad (ver permissions.py). Va DEBAJO de login_required_with_tenant."""
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not can(current_user.role, capability):
                if _wants_json():
                    return jsonify({'error': 'No tenés permiso para esta acción.'}), 403
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return wrapper


def superadmin_required(f):
    """
    Solo el administrador de la plataforma. A cualquier otra persona (o a un visitante) le
    responde 404, como si la sección no existiera: no se revela que hay un panel.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not (current_user.is_authenticated and current_user.is_superadmin
                and current_user.is_active and current_user.is_email_confirmed):
            abort(404)
        return f(*args, **kwargs)
    return decorated
