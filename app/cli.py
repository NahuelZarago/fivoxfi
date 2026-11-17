"""Comandos de consola. Se usan con:  flask --app run <comando>"""
import click
from flask.cli import with_appcontext

from .extensions import db


def _find(email):
    from .models.user import User
    user = User.query.filter_by(email=email.strip().lower()).first()
    if user is None:
        raise click.ClickException(f'No existe ninguna cuenta con el email {email}. Registrate primero desde la web.')
    return user


@click.command('make-admin')
@click.argument('email')
@with_appcontext
def make_admin(email):
    """Convierte una cuenta existente en administradora de la plataforma."""
    user = _find(email)
    user.is_superadmin = True
    user.is_email_confirmed = True      # El admin es quien corre este comando: la cuenta es de confianza
    user.is_active = True
    user.auth_version += 1              # Cierra sus sesiones abiertas para que vuelva a entrar
    db.session.commit()
    click.echo(f'Listo: {user.email} ahora es administrador. Entrá a /admin.')


@click.command('remove-admin')
@click.argument('email')
@with_appcontext
def remove_admin(email):
    """Le quita el permiso de administrador a una cuenta."""
    user = _find(email)
    user.is_superadmin = False
    user.auth_version += 1
    db.session.commit()
    click.echo(f'{user.email} ya no es administrador.')


def register_cli(app):
    app.cli.add_command(make_admin)
    app.cli.add_command(remove_admin)
