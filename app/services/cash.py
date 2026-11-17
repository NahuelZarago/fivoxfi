"""Caja diaria: abrir, ver el estado en vivo y cerrar con arqueo."""
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.cash_session import CashSession
from ..models.sale import Sale
from ..utils.timeutils import utcnow
from ..utils.validation import ValidationFailure

ZERO = Decimal('0.00')


def current_session(tenant_id):
    return CashSession.query.filter_by(tenant_id=tenant_id, closed_at=None).first()


def open_session(tenant_id, user_id, opening_amount):
    if current_session(tenant_id):
        raise ValidationFailure('Ya hay una caja abierta.')
    try:
        session = CashSession(tenant_id=tenant_id, opened_by_id=user_id, opening_amount=opening_amount,
                              opened_at=utcnow())
        db.session.add(session)
        db.session.commit()
        return session
    except IntegrityError:
        # Dos personas abrieron a la vez: el índice único deja pasar solo a una.
        db.session.rollback()
        raise ValidationFailure('Ya hay una caja abierta.')
    except Exception:
        db.session.rollback()
        raise


def summary(session, now=None):
    """Ventas del turno por medio de pago (sin anuladas) y efectivo esperado en caja."""
    end = session.closed_at or now or utcnow()
    base = [Sale.tenant_id == session.tenant_id, Sale.created_at >= session.opened_at, Sale.created_at <= end]
    rows = (db.session.query(Sale.payment_method, func.sum(Sale.total_amount), func.count(Sale.id))
            .filter(*base, Sale.voided_at.is_(None)).group_by(Sale.payment_method).all())
    methods = [{'method': m, 'total': Decimal(t or 0), 'count': int(n)} for m, t, n in rows]
    methods.sort(key=lambda r: r['method'])
    cash_sales = sum((r['total'] for r in methods if r['method'] == 'cash'), ZERO)
    voided = db.session.query(func.count(Sale.id)).filter(*base, Sale.voided_at.isnot(None)).scalar() or 0
    return {
        'methods': methods,
        'total': sum((r['total'] for r in methods), ZERO),
        'count': sum(r['count'] for r in methods),
        'cash_sales': cash_sales,
        'voided': int(voided),
        'expected_cash': Decimal(session.opening_amount) + cash_sales,
    }


def close_session(tenant_id, user_id, counted_cash, note=None):
    """Cierra la caja abierta. Devuelve la CashSession cerrada (con expected_cash y counted_cash guardados)."""
    try:
        session = (CashSession.query.filter_by(tenant_id=tenant_id, closed_at=None)
                   .with_for_update().first())
        if session is None:
            raise ValidationFailure('No hay una caja abierta.')
        now = utcnow()
        session.expected_cash = summary(session, now)['expected_cash']
        session.counted_cash = counted_cash
        session.closed_at, session.closed_by_id, session.note = now, user_id, note or None
        db.session.commit()
        return session
    except Exception:
        db.session.rollback()
        raise
