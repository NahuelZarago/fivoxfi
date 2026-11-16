"""Formato de dinero y fechas para mostrar al usuario (convención argentina)."""
from decimal import Decimal, InvalidOperation

from .timeutils import to_local


def format_money(value, decimals=2):
    """Decimal('1234.5') -> '$1.234,50'. Con decimals=0 -> '$1.235'."""
    try:
        number = Decimal(str(value if value is not None else 0))
    except InvalidOperation:
        number = Decimal(0)
    quant = Decimal(1).scaleb(-decimals)  # 2 -> 0.01, 0 -> 1
    text = f'{number.quantize(quant):,.{decimals}f}'
    # '1,234.50' -> '1.234,50' (cambiar separadores sin pisarse)
    return '$' + text.replace(',', '\0').replace('.', ',').replace('\0', '.')


def format_money0(value):
    return format_money(value, 0)


def format_local_dt(value, fmt='%d/%m/%Y %H:%M'):
    """Fecha guardada en UTC -> texto en hora de Argentina."""
    local = to_local(value)
    return local.strftime(fmt) if local else '—'
