"""Utilidades de texto."""
import re
import unicodedata


def slugify(text, max_length=60):
    """'Panadería Sol & Cía' -> 'panaderia-sol-cia'. Nunca devuelve vacío."""
    ascii_text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', ascii_text).strip('-').lower()
    return slug[:max_length].strip('-') or 'negocio'


def escape_like(value):
    """
    Escapa % y _ para usar texto del usuario dentro de un LIKE/ILIKE
    (con escape='\\'). Sin esto, buscar "%" devuelve todo.
    """
    return str(value).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
