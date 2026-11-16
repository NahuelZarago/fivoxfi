"""
Códigos de invitación.

  FX-XXXXXX  -> el usuario se une como EMPLEADO
  FC-XXXXXX  -> el usuario se une como CLIENTE

Se generan con `secrets` (criptográficamente seguros; `random` no lo es).
El alfabeto evita caracteres ambiguos (0/O, 1/I/L) para poder dictarlos.
Los códigos viejos (alfabeto completo) siguen siendo válidos.
"""
import re
import secrets

EMPLOYEE_PREFIX = 'FX'
CLIENT_PREFIX = 'FC'
_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
_BODY_LENGTH = 6


def generate_code(prefix):
    body = ''.join(secrets.choice(_ALPHABET) for _ in range(_BODY_LENGTH))
    return f'{prefix}-{body}'


def generate_employee_code():
    return generate_code(EMPLOYEE_PREFIX)


def generate_client_code():
    return generate_code(CLIENT_PREFIX)


def normalize_code(raw):
    """
    Tolera cómo lo escriba la persona: minúsculas, espacios, sin guion.
        ' fx a3k9b2 ' -> 'FX-A3K9B2'
    Devuelve None si no tiene el formato de un código.
    """
    cleaned = re.sub(r'[^A-Za-z0-9]', '', str(raw or '')).upper()
    if len(cleaned) == 2 + _BODY_LENGTH and cleaned[:2] in (EMPLOYEE_PREFIX, CLIENT_PREFIX):
        return f'{cleaned[:2]}-{cleaned[2:]}'
    return None
