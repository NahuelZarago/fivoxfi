"""Redirecciones seguras."""
from urllib.parse import urlparse


def safe_next_url(target, fallback):
    """
    Devuelve `target` solo si es una ruta interna del sitio; si no, `fallback`.

    Evita el "open redirect": un enlace como /auth/login?next=https://sitio-malo.com
    no debe llevar al usuario a otro dominio después de iniciar sesión.
    """
    if not target:
        return fallback
    target = str(target).strip()
    if not target.startswith('/') or target.startswith('//') or target.startswith('/\\'):
        return fallback
    # Los navegadores ignoran tabs y saltos de línea dentro de las URLs:
    # "/\t/sitio-malo.com" se interpretaría como "//sitio-malo.com".
    if any(ord(char) < 32 or ord(char) == 127 for char in target):
        return fallback
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return fallback
    return target
