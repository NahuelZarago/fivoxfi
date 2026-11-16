"""
Manejo de fechas. La base guarda todo en UTC "naive" (sin zona); el negocio
piensa en hora de Argentina (UTC-3, sin horario de verano).

Por qué importa: con `datetime.utcnow()` las ventas hechas después de las
21:00 caían en el día siguiente en los reportes y el "cierre de caja".
Se usa un offset fijo en vez de zoneinfo para no depender del paquete `tzdata`
en Windows. Si un día se soportan otros países, este es el único lugar a cambiar.
"""
from datetime import date, datetime, timedelta, timezone

LOCAL_TZ = timezone(timedelta(hours=-3), 'ART')

WEEKDAYS_ES = ('Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom')


def utcnow():
    """Ahora en UTC, sin tzinfo (formato de las columnas DateTime del proyecto)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_local(value):
    """UTC (naive o aware) -> datetime con hora de Argentina. None -> None."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TZ)


def _local_to_utc_naive(local_dt):
    return local_dt.astimezone(timezone.utc).replace(tzinfo=None)


def local_midnight_utc(days_ago=0, now=None):
    """Medianoche local de hace `days_ago` días, expresada en UTC naive."""
    local = to_local(now or utcnow())
    start = (local - timedelta(days=days_ago)).replace(hour=0, minute=0, second=0, microsecond=0)
    return _local_to_utc_naive(start)


def local_month_start_utc(now=None):
    """Primer instante del mes actual (hora local), en UTC naive."""
    local = to_local(now or utcnow())
    return _local_to_utc_naive(local.replace(day=1, hour=0, minute=0, second=0, microsecond=0))


def local_day_bounds_utc(day):
    """[inicio, fin) de un día local (objeto date), en UTC naive."""
    start = datetime(day.year, day.month, day.day, tzinfo=LOCAL_TZ)
    return _local_to_utc_naive(start), _local_to_utc_naive(start + timedelta(days=1))


def local_today(now=None):
    return to_local(now or utcnow()).date()


def parse_local_date(raw, default=None):
    """'2026-11-16' -> date. Si es inválido, devuelve `default`."""
    try:
        return date.fromisoformat(str(raw).strip())
    except (ValueError, TypeError):
        return default
