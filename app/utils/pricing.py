"""Cálculo de precios para la actualización masiva. Puro: sin base de datos."""
from decimal import ROUND_HALF_UP, Decimal

from .validation import CENT, MAX_MONEY, ValidationFailure

# clave del formulario -> múltiplo al que se redondea (None = solo centavos)
ROUNDING_OPTIONS = {
    'none': (None, 'Sin redondeo (centavos)'),
    '1': (Decimal('1'), 'Al peso'),
    '10': (Decimal('10'), 'A múltiplos de $10'),
    '50': (Decimal('50'), 'A múltiplos de $50'),
    '100': (Decimal('100'), 'A múltiplos de $100'),
}
APPLIES_TO = {
    'sale': 'Solo precio de venta',
    'cost': 'Solo precio de compra (costo)',
    'both': 'Venta y compra',
}


def compute_new_price(old, percent, step=None):
    """
    old * (1 + percent/100), redondeado a centavos (mitad hacia arriba) y luego,
    si hay `step`, al múltiplo más cercano. Nunca devuelve negativos ni más que MAX_MONEY.
    """
    old = Decimal(old)
    new = (old * (Decimal('100') + Decimal(percent)) / Decimal('100')).quantize(CENT, rounding=ROUND_HALF_UP)
    if step:
        new = ((new / step).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * step).quantize(CENT)
    if new < 0:
        new = Decimal('0.00')
    if new > MAX_MONEY:
        raise ValidationFailure('Un precio superaría el máximo permitido con ese porcentaje.')
    return new
