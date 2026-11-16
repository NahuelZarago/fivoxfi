from flask import current_app, render_template, url_for
from flask_mail import Message
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..extensions import mail

SALT_VERIFY = 'email-verify-v3'
SALT_RESET = 'password-reset-v3'
VERIFY_MAX_AGE = 3600
RESET_MAX_AGE = 3600


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def make_token(payload, salt):
    return _serializer().dumps(payload, salt=salt)


def read_token(token, salt, max_age):
    """Devuelve (payload, error) donde error es None | 'expired' | 'invalid'."""
    try:
        return _serializer().loads(token, salt=salt, max_age=max_age), None
    except SignatureExpired:
        return None, 'expired'
    except BadSignature:
        return None, 'invalid'


def _send(subject, recipient, template, **ctx):
    if not current_app.config.get('MAIL_USERNAME'):
        return False, 'El envío de emails no está configurado en el servidor.'
    try:
        msg = Message(subject=subject, recipients=[recipient])
        msg.html = render_template(template, **ctx)
        mail.send(msg)
        return True, ''
    except Exception:  # noqa: BLE001 - nunca filtrar detalles SMTP al usuario
        current_app.logger.exception('Error enviando email a un usuario (id oculto)')
        return False, 'No pudimos enviar el email. Intentá de nuevo en unos minutos.'


def send_verification_email(user):
    token = make_token(user.email, SALT_VERIFY)
    url = url_for('auth.verify_email', token=token, _external=True)
    return _send('Verificá tu cuenta en Fivox', user.email, 'email/verify.html',
                 username=user.username, url=url)


def send_password_reset_email(user):
    # auth_version en el token: una vez usado (cambia la contraseña) deja de servir.
    token = make_token({'id': user.id, 'v': user.auth_version}, SALT_RESET)
    url = url_for('auth.reset_password', token=token, _external=True)
    return _send('Restablecé tu contraseña de Fivox', user.email, 'email/reset.html',
                 username=user.username, url=url)
