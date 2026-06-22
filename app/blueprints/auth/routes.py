import re
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from . import auth_bp
from ...extensions import db, mail
from ...models.tenant import Tenant, generate_employee_code
from ...models.user import User


# ─── Helpers ───────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^\w-]', '', text)
    return text


def get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def send_verification_email(user: User):
    """Envía el correo de verificación de email."""
    s = get_serializer()
    token = s.dumps(user.email, salt='email-verify-2024')
    verify_url = url_for('auth.verify_email', token=token, _external=True)

    msg = Message(subject='Verificá tu email — Fivox', recipients=[user.email])
    msg.html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, sans-serif; background: #f9fafb; margin: 0; padding: 40px 20px;">
      <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 16px;
                  border: 1px solid #e5e7eb; padding: 40px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:28px;">
          <div style="width:36px;height:36px;background:#16a34a;border-radius:10px;display:flex;
                      align-items:center;justify-content:center;">
            <span style="color:white;font-size:18px;font-weight:bold;">F</span>
          </div>
          <span style="font-size:20px;font-weight:800;color:#111827;">Fivox</span>
        </div>
        <h2 style="font-size:22px;font-weight:700;color:#111827;margin:0 0 8px;">
          Hola, {user.username} 👋
        </h2>
        <p style="color:#6b7280;font-size:15px;line-height:1.6;margin:0 0 28px;">
          Gracias por registrarte. Para activar tu cuenta hacé clic en el botón:
        </p>
        <a href="{verify_url}"
           style="display:block;background:#16a34a;color:white;text-align:center;
                  padding:14px 28px;border-radius:12px;text-decoration:none;
                  font-weight:700;font-size:15px;margin-bottom:24px;">
          ✓ Verificar mi email
        </a>
        <p style="color:#9ca3af;font-size:13px;line-height:1.5;border-top:1px solid #f3f4f6;
                  padding-top:20px;margin:0;">
          Este enlace expira en <strong>1 hora</strong>.<br>
          Si no creaste esta cuenta, ignorá este mensaje.
        </p>
      </div>
    </body>
    </html>
    """
    mail.send(msg)


# ─── Registro ──────────────────────────────────────────────────────────────

@auth_bp.route('/registro', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated and current_user.is_email_confirmed and current_user.has_role:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # Validaciones
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
            flash('Ya existe una cuenta con ese email.', 'danger')
            return render_template('auth/register.html')

        try:
            user = User(email=email, username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            # Enviar email de verificación
            send_verification_email(user)

            # Loguear pero sin acceso completo hasta verificar
            login_user(user)
            flash('¡Cuenta creada! Revisá tu correo para verificar tu email.', 'success')
            return redirect(url_for('auth.pending_verification'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error registro: {e}')
            flash('Error inesperado. Intentá de nuevo.', 'danger')

    return render_template('auth/register.html')


# ─── Verificación pendiente ─────────────────────────────────────────────────

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
    try:
        send_verification_email(current_user)
        flash('Correo de verificación reenviado. Revisá tu casilla.', 'success')
    except Exception as e:
        current_app.logger.error(f'Error reenvío email: {e}')
        flash('No se pudo reenviar. Verificá la configuración de email.', 'danger')
    return redirect(url_for('auth.pending_verification'))


# ─── Verificar email (desde el enlace del correo) ──────────────────────────

@auth_bp.route('/verificar/<token>')
def verify_email(token):
    s = get_serializer()
    try:
        email = s.loads(token, salt='email-verify-2024', max_age=3600)
    except SignatureExpired:
        flash('El enlace expiró. Solicitá uno nuevo iniciando sesión.', 'danger')
        return redirect(url_for('auth.login'))
    except BadSignature:
        flash('Enlace inválido.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('No se encontró la cuenta.', 'danger')
        return redirect(url_for('auth.register'))

    if not user.is_email_confirmed:
        user.is_email_confirmed = True
        db.session.commit()

    # Loguearlo si no lo está
    if not current_user.is_authenticated:
        login_user(user)

    flash('¡Email verificado correctamente! Ahora elegí cómo querés usar Fivox.', 'success')
    return redirect(url_for('auth.choose_role'))


# ─── Elegir rol (después de verificar email) ───────────────────────────────

@auth_bp.route('/elegir-rol', methods=['GET', 'POST'])
@login_required
def choose_role():
    # Si no verificó email, mandarlo a verificación
    if not current_user.is_email_confirmed:
        return redirect(url_for('auth.pending_verification'))

    # Si ya eligió rol, mandarlo al dashboard
    if current_user.has_role and current_user.tenant_id:
        return redirect(url_for('dashboard.index'))

    return render_template('auth/choose_role.html')


# ─── Setup Owner (crea negocio propio) ─────────────────────────────────────

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

        # Slug único
        base_slug = slugify(business_name)
        slug = base_slug
        counter = 1
        while Tenant.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Generar employee_code único
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


# ─── Setup Seller (se une con código de empleado) ──────────────────────────

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
            flash('Código incorrecto o negocio no encontrado. Verificá con tu jefe.', 'danger')
            return render_template('auth/setup_seller.html')

        try:
            current_user.tenant_id = tenant.id
            current_user.role = 'seller'
            db.session.commit()

            flash(f'¡Bienvenido al equipo de {tenant.name}!', 'success')
            return redirect(url_for('pos.terminal'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error setup seller: {e}')
            flash('Error al unirte al negocio. Intentá de nuevo.', 'danger')

    return render_template('auth/setup_seller.html')


# ─── Login ──────────────────────────────────────────────────────────────────

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

        # Redirigir según estado del usuario
        if not user.is_email_confirmed:
            return redirect(url_for('auth.pending_verification'))
        if not user.has_role:
            return redirect(url_for('auth.choose_role'))

        flash(f'¡Hola, {user.username}!', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard.index'))

    return render_template('auth/login.html')


# ─── Logout ─────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('public.index'))
