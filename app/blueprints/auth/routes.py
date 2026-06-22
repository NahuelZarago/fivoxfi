import re
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
from . import auth_bp
from ...extensions import db, mail
from ...models.tenant import Tenant
from ...models.user import User


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^\w-]', '', text)
    return text


@auth_bp.route('/registro', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # Validaciones básicas
        if not all([business_name, username, email, password]):
            flash('Todos los campos son obligatorios.', 'danger')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'danger')
            return render_template('auth/register.html')

        # Generar slug único para el tenant
        base_slug = slugify(business_name)
        slug = base_slug
        counter = 1
        while Tenant.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        try:
            # Crear Tenant y Admin en una sola transacción
            tenant = Tenant(name=business_name, slug=slug)
            db.session.add(tenant)
            db.session.flush()  # Para obtener tenant.id antes del commit

            admin = User(
                tenant_id=tenant.id,
                email=email,
                username=username,
                role='admin'
            )
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()

            # Logueamos al usuario automáticamente
            login_user(admin)

            # 👇 LÓGICA DE ENVÍO DE CORREO 👇
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = serializer.dumps(email, salt='email-confirm')
            # _external=True hace que la URL sea completa (http://...) para que funcione en el mail
            confirm_url = url_for('auth.confirm_email', token=token, _external=True)
            
            msg = Message('Confirma tu cuenta en Fivox', recipients=[email])
            msg.body = f'Hola {username},\n\nPara proteger tu cuenta y activar tu acceso a Fivox, por favor confirmá tu dirección de correo haciendo clic en el siguiente enlace:\n\n{confirm_url}\n\nSi no creaste esta cuenta, ignorá este mensaje.'
            mail.send(msg)

            flash(f'¡Cuenta creada! Te enviamos un correo para verificar tu email.', 'success')
            # Redirigimos a la pantalla de bloqueo en vez de al dashboard
            return redirect(url_for('auth.unconfirmed'))

        except Exception as e:
            db.session.rollback()
            print(f"🔥 ERROR REAL AL REGISTRAR: {str(e)}")
            flash('Error al crear la cuenta. El email ya puede estar registrado.', 'danger')
            return render_template('auth/register.html')

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=request.form.get('remember'))
            next_page = request.args.get('next')
            flash(f'¡Hola, {user.username}!', 'success')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash('Email o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('public.index'))


@auth_bp.route('/cuenta-no-confirmada')
@login_required
def unconfirmed():
    if current_user.is_confirmed:
        return redirect(url_for('dashboard.index'))
    return render_template('auth/unconfirmed.html')


# 👇 NUEVA RUTA PARA PROCESAR EL CLIC DEL CORREO 👇
@auth_bp.route('/confirmar/<token>')
@login_required
def confirm_email(token):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        # El token expira en 3600 segundos (1 hora)
        email = serializer.loads(token, salt='email-confirm', max_age=3600)
    except:
        flash('El enlace de confirmación es inválido o expiró.', 'danger')
        return redirect(url_for('auth.unconfirmed'))

    if current_user.email != email:
        flash('Acceso denegado. Este enlace no corresponde a tu cuenta.', 'danger')
        return redirect(url_for('public.index'))

    if not current_user.is_confirmed:
        current_user.is_confirmed = True
        db.session.commit()
        flash('¡Excelente! Tu cuenta ya está verificada.', 'success')
    
    return redirect(url_for('dashboard.index'))