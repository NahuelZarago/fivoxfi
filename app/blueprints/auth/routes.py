import re
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from . import auth_bp
from ...extensions import db, mail
from ...models.tenant import Tenant, generate_employee_code
from ...models.user import User


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^\w-]', '', text)
    return text


def get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def send_verification_email(user: User) -> tuple[bool, str]:
    """
    Intenta enviar el correo de verificación.
    Retorna (True, '') si tuvo éxito, o (False, mensaje_error) si falló.
    """
    # Verificar que el mail esté configurado antes de intentar enviar
    if not current_app.config.get('MAIL_USERNAME'):
        return False, 'El servidor de email no está configurado. Configurá MAIL_USERNAME en el archivo .env'

    try:
        s = get_serializer()
        token = s.dumps(user.email, salt='email-verify-2024')
        verify_url = url_for('auth.verify_email', token=token, _external=True)

        msg = Message(subject='Verificá tu cuenta en Fivox', recipients=[user.email])
        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;margin:0;padding:32px 16px;">
          <div style="max-width:500px;margin:0 auto;background:white;border-radius:16px;border:1px solid #e5e7eb;overflow:hidden;">
            <div style="background:#16a34a;padding:28px 32px;">
              <div style="display:flex;align-items:center;gap:10px;">
                <div style="width:32px;height:32px;background:rgba(255,255,255,0.2);border-radius:8px;display:flex;align-items:center;justify-content:center;">
                  <span style="color:white;font-size:16px;font-weight:900;">F</span>
                </div>
                <span style="color:white;font-size:20px;font-weight:800;letter-spacing:-0.5px;">Fivox</span>
              </div>
            </div>
            <div style="padding:32px;">
              <h2 style="font-size:22px;font-weight:700;color:#111827;margin:0 0 8px;">Hola, {user.username} 👋</h2>
              <p style="color:#6b7280;font-size:15px;line-height:1.6;margin:0 0 24px;">
                Gracias por registrarte en Fivox. Para activar tu cuenta y empezar a gestionar tu negocio, verificá tu dirección de email:
              </p>
              <a href="{verify_url}"
                 style="display:block;background:#16a34a;color:white;text-align:center;padding:14px 24px;
                        border-radius:12px;text-decoration:none;font-weight:700;font-size:15px;margin-bottom:24px;">
                ✓ Verificar mi email
              </a>
              <div style="background:#f9fafb;border-radius:10px;padding:16px;margin-bottom:24px;">
                <p style="color:#6b7280;font-size:13px;margin:0 0 6px;">O copiá este enlace en tu navegador:</p>
                <p style="color:#374151;font-size:12px;word-break:break-all;margin:0;font-family:monospace;">{verify_url}</p>
              </div>
              <p style="color:#9ca3af;font-size:13px;line-height:1.5;border-top:1px solid #f3f4f6;padding-top:20px;margin:0;">
                Este enlace expira en <strong>1 hora</strong>. Si no creaste esta cuenta, ignorá este mensaje.
              </p>
            </div>
          </div>
        </body>
        </html>
        """
        mail.send(msg)
        return True, ''

    except Exception as e:
        error_msg = str(e)
        current_app.logger.error(f'Error enviando email de verificación a {user.email}: {error_msg}')

        # Dar un mensaje útil según el tipo de error
        if 'Authentication' in error_msg or 'credentials' in error_msg.lower():
            return False, 'Credenciales de email incorrectas. Revisá MAIL_USERNAME y MAIL_PASSWORD en el .env'
        elif 'Connection' in error_msg or 'connect' in error_msg.lower():
            return False, 'No se pudo conectar al servidor de email. Verificá MAIL_SERVER y MAIL_PORT'
        else:
            return False, f'Error de email: {error_msg}'


# ─── REGISTRO ──────────────────────────────────────────────────────────────

@auth_bp.route('/registro', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated and current_user.is_email_confirmed and current_user.has_role:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not all([username, email, password, confirm]):
            flash('Todos los campos son obligatorios.', 'danger')
            return render_template('auth/register.html')
        if password != confirm:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('auth/register.html')
        if len(password) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'danger')
            return render_template('auth/register.html')
        if User.query.filter_by(email=email).first():
            flash('Ya existe una cuenta con ese email. ¿Querés iniciar sesión?', 'warning')
            return render_template('auth/register.html')

        # Crear usuario PRIMERO, luego intentar enviar email
        user = User(email=email, username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Intentar enviar email
        ok, error_msg = send_verification_email(user)

        login_user(user)

        if ok:
            flash('¡Cuenta creada! Revisá tu correo para verificar tu email.', 'success')
        else:
            # Email no llegó, pero la cuenta existe. Mostrar error específico.
            flash(f'Cuenta creada, pero no se pudo enviar el email: {error_msg}', 'warning')
            flash('Podés intentar reenviarlo desde la pantalla de verificación.', 'info')

        return redirect(url_for('auth.pending_verification'))

    return render_template('auth/register.html')


# ─── VERIFICACIÓN PENDIENTE ─────────────────────────────────────────────────

@auth_bp.route('/verificacion-pendiente')
@login_required
def pending_verification():
    if current_user.is_email_confirmed:
        if current_user.has_role:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.choose_role'))
    return render_template('auth/pending_verification.html')


@auth_bp.route('/reenviar-verificacion', methods=['POST'])
@login_required
def resend_verification():
    if current_user.is_email_confirmed:
        return redirect(url_for('dashboard.index'))

    ok, error_msg = send_verification_email(current_user)
    if ok:
        flash('Correo reenviado. Revisá tu bandeja (también spam).', 'success')
    else:
        flash(f'No se pudo enviar: {error_msg}', 'danger')

    return redirect(url_for('auth.pending_verification'))


# ─── VERIFICAR EMAIL ────────────────────────────────────────────────────────

@auth_bp.route('/verificar/<token>')
def verify_email(token):
    s = get_serializer()
    try:
        email = s.loads(token, salt='email-verify-2024', max_age=3600)
    except SignatureExpired:
        flash('El enlace expiró (válido 1 hora). Solicitá uno nuevo.', 'danger')
        return redirect(url_for('auth.login'))
    except BadSignature:
        flash('Enlace inválido o ya utilizado.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('No se encontró la cuenta.', 'danger')
        return redirect(url_for('auth.register'))

    if not user.is_email_confirmed:
        user.is_email_confirmed = True
        db.session.commit()

    if not current_user.is_authenticated:
        login_user(user)

    flash('¡Email verificado! Ahora elegí cómo querés usar Fivox.', 'success')
    return redirect(url_for('auth.choose_role'))


# ─── ELEGIR ROL ─────────────────────────────────────────────────────────────

@auth_bp.route('/elegir-rol')
@login_required
def choose_role():
    if not current_user.is_email_confirmed:
        return redirect(url_for('auth.pending_verification'))
    if current_user.has_role and current_user.tenant_id:
        return redirect(url_for('dashboard.index'))
    return render_template('auth/choose_role.html')


# ─── SETUP OWNER ────────────────────────────────────────────────────────────

@auth_bp.route('/setup-owner', methods=['GET', 'POST'])
@login_required
def setup_owner():
    if not current_user.is_email_confirmed:
        return redirect(url_for('auth.pending_verification'))
    if current_user.has_role and current_user.tenant_id:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip()
        if not business_name:
            flash('El nombre del negocio es obligatorio.', 'danger')
            return render_template('auth/setup_owner.html')

        base_slug = slugify(business_name)
        slug = base_slug
        counter = 1
        while Tenant.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        code = generate_employee_code()
        while Tenant.query.filter_by(employee_code=code).first():
            code = generate_employee_code()

        try:
            tenant = Tenant(name=business_name, slug=slug, employee_code=code)
            db.session.add(tenant)
            db.session.flush()
            current_user.tenant_id = tenant.id
            current_user.role = 'owner'
            db.session.commit()
            flash(f'¡Negocio "{business_name}" creado! Bienvenido a Fivox.', 'success')
            return redirect(url_for('dashboard.index'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error setup owner: {e}')
            flash('Error al crear el negocio. Intentá de nuevo.', 'danger')

    return render_template('auth/setup_owner.html')


# ─── SETUP SELLER ───────────────────────────────────────────────────────────

@auth_bp.route('/setup-empleado', methods=['GET', 'POST'])
@login_required
def setup_seller():
    if not current_user.is_email_confirmed:
        return redirect(url_for('auth.pending_verification'))
    if current_user.has_role and current_user.tenant_id:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        code = request.form.get('employee_code', '').strip().upper()
        if not code:
            flash('Ingresá el código de empleado.', 'danger')
            return render_template('auth/setup_seller.html')

        tenant = Tenant.query.filter_by(employee_code=code, is_active=True).first()
        if not tenant:
            flash('Código incorrecto. Verificá con tu empleador.', 'danger')
            return render_template('auth/setup_seller.html')

        try:
            current_user.tenant_id = tenant.id
            current_user.role = 'seller'
            db.session.commit()
            flash(f'¡Bienvenido al equipo de {tenant.name}!', 'success')
            return redirect(url_for('pos.terminal'))
        except Exception as e:
            db.session.rollback()
            flash('Error al unirte al negocio. Intentá de nuevo.', 'danger')

    return render_template('auth/setup_seller.html')


# ─── LOGIN ──────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if not current_user.is_email_confirmed:
            return redirect(url_for('auth.pending_verification'))
        if not current_user.has_role:
            return redirect(url_for('auth.choose_role'))
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Email o contraseña incorrectos.', 'danger')
            return render_template('auth/login.html')
        if not user.is_active:
            flash('Tu cuenta fue desactivada. Contactá al dueño del negocio.', 'danger')
            return render_template('auth/login.html')

        login_user(user, remember=bool(request.form.get('remember')))

        if not user.is_email_confirmed:
            return redirect(url_for('auth.pending_verification'))
        if not user.has_role:
            return redirect(url_for('auth.choose_role'))

        flash(f'¡Hola, {user.username}!', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard.index'))

    return render_template('auth/login.html')


# ─── LOGOUT ─────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('public.index'))
