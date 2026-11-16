"""
Validación y parseo de datos de formularios.

Regla del proyecto: el dinero es siempre Decimal, nunca float. Todo lo que
llega del navegador se valida acá y los errores salen como ValidationFailure
con un mensaje listo para mostrarle al usuario.
"""
import re
from decimal import Decimal, InvalidOperation

CENT = Decimal('0.01')
MAX_MONEY = Decimal('99999999.99')  # Límite de la columna Numeric(10, 2)
MAX_QUANTITY = 1_000_000

_EMAIL_RE = re.compile(r'^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$')
_MONEY_RE = re.compile(r'^\d+(\.\d+)?$')
_INT_RE = re.compile(r'^-?\d{1,9}$')


class ValidationFailure(ValueError):
    """Dato inválido. str(error) es apto para mostrar al usuario."""


def parse_money(raw, label='El monto'):
    """
    '1234.5' | '1234,50' | '1.234,50' | '$ 1234' -> Decimal('1234.50')
    Rechaza vacíos, NaN, infinitos, negativos, más de 2 decimales y montos
    que no entran en Numeric(10, 2).
    """
    text = '' if raw is None else str(raw).strip().replace(' ', '').replace('$', '')
    if not text:
        raise ValidationFailure(f'{label} es obligatorio.')
    if ',' in text:  # Formato argentino: el punto separa miles y la coma decimales
        text = text.replace('.', '').replace(',', '.')
    if not _MONEY_RE.match(text.lstrip('-')):  # Rechaza notación científica, 'NaN', 'inf', etc.
        raise ValidationFailure(f'{label} no es un número válido.')
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValidationFailure(f'{label} no es un número válido.') from None
    if not value.is_finite():  # Antes de comparar: NaN rompe las comparaciones
        raise ValidationFailure(f'{label} no es un número válido.')
    if value < 0:
        raise ValidationFailure(f'{label} no puede ser negativo.')
    if value > MAX_MONEY:
        raise ValidationFailure(f'{label} es demasiado grande.')
    quantized = value.quantize(CENT)
    if quantized != value:
        raise ValidationFailure(f'{label} admite hasta 2 decimales.')
    return Decimal('0.00') if quantized == 0 else quantized  # Evita "-0.00"


def parse_int(raw, label='El valor', minimum=0, maximum=MAX_QUANTITY):
    text = '' if raw is None else str(raw).strip()
    if not text:
        raise ValidationFailure(f'{label} es obligatorio.')
    if not _INT_RE.match(text):
        raise ValidationFailure(f'{label} debe ser un número entero.')
    value = int(text)
    if value < minimum:
        raise ValidationFailure(f'{label} no puede ser menor a {minimum}.')
    if value > maximum:
        raise ValidationFailure(f'{label} no puede ser mayor a {maximum}.')
    return value


def clean_text(raw, label, min_len=1, max_len=200, required=True):
    """Recorta espacios y valida el largo. Devuelve None si es opcional y está vacío."""
    text = ' '.join(str(raw or '').split())  # Colapsa espacios y saltos de línea
    if not text:
        if required:
            raise ValidationFailure(f'{label} es obligatorio.')
        return None
    if len(text) < min_len:
        raise ValidationFailure(f'{label} debe tener al menos {min_len} caracteres.')
    if len(text) > max_len:
        raise ValidationFailure(f'{label} no puede superar los {max_len} caracteres.')
    return text


def clean_multiline(raw, label, max_len=1000):
    text = str(raw or '').strip()
    if len(text) > max_len:
        raise ValidationFailure(f'{label} no puede superar los {max_len} caracteres.')
    return text or None


def validate_email(raw):
    email = str(raw or '').strip().lower()
    if not email:
        raise ValidationFailure('El email es obligatorio.')
    if len(email) > 120 or not _EMAIL_RE.match(email):
        raise ValidationFailure('Ingresá un email válido, por ejemplo nombre@empresa.com.')
    return email


def validate_password(raw):
    """8 a 128 caracteres, con al menos una letra y un número."""
    password = str(raw or '')
    if len(password) < 8:
        raise ValidationFailure('La contraseña debe tener al menos 8 caracteres.')
    if len(password) > 128:  # Evita enviar contraseñas enormes al hasheo
        raise ValidationFailure('La contraseña no puede superar los 128 caracteres.')
    if not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
        raise ValidationFailure('La contraseña debe incluir al menos una letra y un número.')
    return password
