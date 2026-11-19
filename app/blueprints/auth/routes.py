import hmac
from datetime import datetime

from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from . import auth_bp
from ...extensions import db, limiter
from ...models.user import User
from ...services.google_oauth import login_or_create
from ...services.tenants import create_tenant_for_owner, join_with_code
from ...utils import google_auth as google
from ...utils.csrf import rotate_csrf_token
from ...utils.legal import TERMS_VERSION
from ...utils.mailer import (
    RESET_MAX_AGE, SALT_RESET, SALT_VERIFY, VERIFY_MAX_AGE, read_token,
    send_password_reset_email, send_verification_email)
from ...utils.permissions import home_endpoint
from ...utils.urls import safe_next_url
from ...utils.validation import (
    ValidationFailure, clean_text, validate_email, validate_password)

# Hash falso para que el login tarde lo mismo exista o no el email.
_DUMMY_HASH = generate_password_hash('not-a-real-password')


def _after_auth_redirect(user):
    """Dónde debe estar un usuario según cuán completo está su perfil."""
    if not user.is_email_confirmed:
        return redirect(url_for('auth.pending_verification'))
    if not user.has_role or not user.tenant_id:
        if user.is_superadmin:
            return redirect(url_for('admin.index'))
        return redirect(url_for('auth.choose_role'))
    return redirect(url_for(home_endpoint(user.role)))


@auth_bp.route('/inicio')
@login_required
def home():
    return _after_auth_redirect(current_user)


# ─── REGISTRO ───────────────────────────────────────────────
@auth_bp.route('/registro', methods=['GET', 'POST'])
@limiter.limit('10 per hour', methods=['POST'])
def register():
    if current_user.is_authenticated:
        return _after_auth_redirect(current_user)

    form, errors = {}, {}
    if request.method == 'POST':
        form = {'username': request.form.get('username', ''), 'email': request.form.get('email', ''),
                'accept_terms': request.form.get('accept_terms') == '1'}
        password = request.form.get('password', '')
        username = email = None

        # Cada campo se valida por separado para mostrar TODOS los errores a la vez, debajo de cada uno.
        for key, check in (
            ('username', lambda: clean_text(form['username'], 'El nombre', max_len=80)),
            ('email', lambda: validate_email(form['email'])),
            ('password', lambda: validate_password(password)),
        ):
            try:
                value = check()
                if key == 'username':
                    username = value
                elif key == 'email':
                    email = value
            except ValidationFailure as exc:
                errors[key] = str(exc)
        if 'password' not in errors and password != request.form.get('confirm_password', ''):
            errors['confirm_password'] = 'Las contraseñas no coinciden.'
        if not form['accept_terms']:
            errors['accept_terms'] = 'Tenés que aceptar los Términos y Condiciones para crear tu cuenta.'
        if email and 'email' not in errors and User.query.filter_by(email=email).first():
            errors['email'] = 'Ya existe una cuenta con ese email. ¿Querés iniciar sesión?'

        if errors:
            return render_template('auth/register.html', form=form, errors=errors), 400

        user = User(email=email, username=username, terms_accepted_at=datetime.utcnow(), terms_version=TERMS_VERSION)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        ok, error = send_verification_email(user)
        login_user(user)
        rotate_csrf_token()
        if ok:
            flash('¡Cuenta creada! Revisá tu correo para verificar tu email.', 'success')
        else:
            flash(f'Cuenta creada, pero {error[0].lower() + error[1:]}', 'warning')
            flash('Podés reintentar el envío desde esta pantalla.', 'info')
        return redirect(url_for('auth.pending_verification'))

    return render_template('auth/register.html', form=form, errors=errors)


# ─── VERIFICACIÓN DE EMAIL ──────────────────────────────────
@auth_bp.route('/verificacion-pendiente')
@login_required
def pending_verification():
    if current_user.is_email_confirmed:
        return _after_auth_redirect(current_user)
    return render_template('auth/pending_verification.html')


@auth_bp.route('/reenviar-verificacion', methods=['POST'])
@login_required
@limiter.limit('3 per hour')
def resend_verification():
    if current_user.is_email_confirmed:
        return _after_auth_redirect(current_user)
    ok, error = send_verification_email(current_user)
    flash('Correo reenviado. Revisá tu bandeja (y spam).' if ok else error, 'success' if ok else 'danger')
    return redirect(url_for('auth.pending_verification'))


@auth_bp.route('/verificar/<token>')
def verify_email(token):
    email, err = read_token(token, SALT_VERIFY, VERIFY_MAX_AGE)
    if err == 'expired':
        flash('El enlace expiró. Pedí uno nuevo desde tu cuenta.', 'danger')
        return redirect(url_for('auth.login'))
    if err or not isinstance(email, str):
        flash('Enlace inválido.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if user is None:
        flash('No se encontró la cuenta.', 'danger')
        return redirect(url_for('auth.register'))
    if not user.is_email_confirmed:
        user.is_email_confirmed = True
        db.session.commit()
    if not current_user.is_authenticated:
        login_user(user)
        rotate_csrf_token()
    flash('¡Email verificado!', 'success')
    return _after_auth_redirect(user)


# ─── ELEGIR ROL / ONBOARDING ────────────────────────────────
def _onboarding_guard():
    """None si el usuario puede onboardear; si no, la redirección correcta."""
    if not current_user.is_email_confirmed:
        return redirect(url_for('auth.pending_verification'))
    if current_user.has_role and current_user.tenant_id:
        return redirect(url_for(home_endpoint(current_user.role)))
    return None


@auth_bp.route('/elegir-rol')
@login_required
def choose_role():
    return _onboarding_guard() or render_template('auth/choose_role.html')


@auth_bp.route('/setup-owner', methods=['GET', 'POST'])
@login_required
@limiter.limit('10 per hour', methods=['POST'])
def setup_owner():
    guard = _onboarding_guard()
    if guard:
        return guard
    if request.method == 'POST':
        try:
            name = clean_text(request.form.get('business_name', ''), 'Nombre del negocio', max_len=120)
            tenant = create_tenant_for_owner(current_user, name)
        except ValidationFailure as exc:
            flash(str(exc), 'danger')
            return render_template('auth/setup_owner.html'), 400
        flash(f'¡Negocio "{tenant.name}" creado! Bienvenido a Fivox.', 'success')
        return redirect(url_for('dashboard.index'))
    return render_template('auth/setup_owner.html')


@auth_bp.route('/unirme', methods=['GET', 'POST'])
@login_required
@limiter.limit('10 per hour', methods=['POST'])   # Evita adivinar códigos por fuerza bruta
def join():
    guard = _onboarding_guard()
    if guard:
        return guard
    if request.method == 'POST':
        try:
            tenant = join_with_code(current_user, request.form.get('code', ''),
                                    employee_limits=current_app.config['PLAN_EMPLOYEE_LIMITS'])
        except ValidationFailure as exc:
            db.session.rollback()
            flash(str(exc), 'danger')
            return render_template('auth/join.html'), 400
        flash(f'¡Te uniste a {tenant.name} como {current_user.role_label.lower()}!', 'success')
        return redirect(url_for(home_endpoint(current_user.role)))
    return render_template('auth/join.html')


# ─── LOGIN / LOGOUT ─────────────────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute; 50 per hour', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return _after_auth_redirect(current_user)

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        valid = check_password_hash(user.password_hash if user else _DUMMY_HASH, password) and user is not None

        if not valid:
            return render_template('auth/login.html', email=email,
                                   error='Email o contraseña incorrectos.'), 401
        if not user.is_active:
            return render_template('auth/login.html', email=email,
                                   error='Tu cuenta fue desactivada. Contactá al dueño del negocio.'), 403

        login_user(user, remember=bool(request.form.get('remember')))
        rotate_csrf_token()
        if not user.is_email_confirmed or not user.has_role:
            return _after_auth_redirect(user)
        flash(f'¡Hola, {user.username}!', 'success')
        fallback = url_for(home_endpoint(user.role))
        return redirect(safe_next_url(request.args.get('next'), fallback))

    return render_template('auth/login.html', email='', error=None)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    logout_user()
    rotate_csrf_token()
    flash('Cerraste sesión.', 'info')
    return redirect(url_for('public.index'))


# ─── RECUPERAR CONTRASEÑA ───────────────────────────────────
@auth_bp.route('/olvide-mi-contrasena', methods=['GET', 'POST'])
@limiter.limit('5 per hour', methods=['POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email, is_active=True).first() if email else None
        if user:
            send_password_reset_email(user)
        # Misma respuesta exista o no la cuenta: no revela qué emails están registrados.
        flash('Si el email está registrado, te enviamos un enlace para elegir una nueva contraseña.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/forgot_password.html')


@auth_bp.route('/restablecer/<token>', methods=['GET', 'POST'])
@limiter.limit('10 per hour', methods=['POST'])
def reset_password(token):
    data, err = read_token(token, SALT_RESET, RESET_MAX_AGE)
    user = None
    if not err and isinstance(data, dict):
        user = db.session.get(User, data.get('id'))
        if user is None or user.auth_version != data.get('v') or not user.is_active:
            user = None
    if user is None:
        flash('El enlace no es válido, venció o ya fue usado. Pedí uno nuevo.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        try:
            password = request.form.get('password', '')
            validate_password(password)
            if password != request.form.get('confirm_password', ''):
                raise ValidationFailure('Las contraseñas no coinciden.')
        except ValidationFailure as exc:
            field = 'confirm_password' if 'coinciden' in str(exc) else 'password'
            return render_template('auth/reset_password.html', token=token, errors={field: str(exc)}), 400
        user.set_password(password)
        user.auth_version += 1          # Invalida el enlace usado y todas las sesiones abiertas
        user.is_email_confirmed = True  # Recibió un email en esa casilla: queda verificado
        db.session.commit()
        flash('Contraseña actualizada. Ya podés iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html', token=token, errors={})


# ─── INICIO DE SESIÓN CON GOOGLE ────────────────────────────
def _google_redirect_uri():
    return current_app.config.get('GOOGLE_REDIRECT_URI') or url_for('auth.google_callback', _external=True)


@auth_bp.route('/google')
@limiter.limit('30 per hour')
def google_start():
    if current_user.is_authenticated:
        return _after_auth_redirect(current_user)
    if not google.is_configured(current_app.config):
        flash('El inicio de sesión con Google no está disponible.', 'warning')
        return redirect(url_for('auth.login'))
    state = google.new_state()
    verifier, challenge = google.pkce_pair()
    session['google_oauth'] = {'state': state, 'verifier': verifier}
    return redirect(google.build_auth_url(current_app.config['GOOGLE_CLIENT_ID'], _google_redirect_uri(),
                                          state, challenge))


@auth_bp.route('/google/callback')
@limiter.limit('30 per hour')
def google_callback():
    saved = session.pop('google_oauth', None)        # De un solo uso
    if current_user.is_authenticated:
        return _after_auth_redirect(current_user)
    if request.args.get('error'):
        flash('Cancelaste el inicio de sesión con Google.', 'info')
        return redirect(url_for('auth.login'))
    state, code = request.args.get('state', ''), request.args.get('code', '')
    if (not google.is_configured(current_app.config) or not isinstance(saved, dict) or not code or not state
            or not hmac.compare_digest(str(saved.get('state', '')), state)):
        flash('La sesión con Google expiró o no es válida. Probá de nuevo.', 'danger')
        return redirect(url_for('auth.login'))
    try:
        token = google.exchange_code(current_app.config['GOOGLE_CLIENT_ID'], current_app.config['GOOGLE_CLIENT_SECRET'],
                                     code, _google_redirect_uri(), saved.get('verifier', ''))
        profile = google.parse_profile(google.fetch_userinfo(token))
        user, created = login_or_create(profile)
    except google.GoogleAuthError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('auth.login'))

    login_user(user)
    rotate_csrf_token()
    if created:
        flash('¡Cuenta creada con Google! Ahora elegí cómo vas a usar Fivox.', 'success')
    elif user.has_role and user.tenant_id:
        flash(f'¡Hola, {user.username}!', 'success')
    return _after_auth_redirect(user)
