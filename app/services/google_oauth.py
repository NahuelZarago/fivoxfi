"""Alta e inicio de sesión de cuentas que entran con Google (la parte con base de datos)."""
import secrets

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.user import User
from ..utils.google_auth import GoogleAuthError


def login_or_create(profile):
    """
    Devuelve (usuario, creado). Busca primero por el id de Google y después por email.
    Si la cuenta existía SIN email verificado, se vuelve a verificar y se anula su contraseña: así
    nadie que se haya registrado antes con un email ajeno conserva acceso a esa cuenta.
    """
    user = User.query.filter_by(google_sub=profile['sub']).first()
    by_email = user or User.query.filter_by(email=profile['email']).first()
    user = user or by_email
    try:
        if user is not None:
            if user.google_sub and user.google_sub != profile['sub']:
                raise GoogleAuthError('Ese email ya está vinculado a otra cuenta de Google.')
            if not user.is_active:
                raise GoogleAuthError('Tu cuenta fue desactivada. Contactá al dueño del negocio.')
            if not user.is_email_confirmed:
                user.is_email_confirmed = True
                user.set_password(secrets.token_urlsafe(32))
                user.auth_version += 1
            user.google_sub = profile['sub']
            db.session.commit()
            return user, False
        user = User(email=profile['email'], username=profile['name'], google_sub=profile['sub'],
                    is_email_confirmed=True)
        user.set_password(secrets.token_urlsafe(32))      # contraseña inutilizable: entra con Google
        db.session.add(user)
        db.session.commit()
        return user, True
    except IntegrityError:
        db.session.rollback()
        raise GoogleAuthError('No pudimos crear tu cuenta. Probá de nuevo.')
    except GoogleAuthError:
        db.session.rollback()
        raise
