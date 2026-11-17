from datetime import datetime

from ..extensions import db


class CashSession(db.Model):
    """
    Un turno de caja: se abre con un monto inicial en efectivo y se cierra contando el efectivo.
    `expected_cash` se guarda al cerrar (queda como foto: anular ventas después no lo cambia).
    Solo puede haber UNA caja abierta por negocio (índice único parcial).
    """
    __tablename__ = 'cash_sessions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    opened_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    closed_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    opened_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)
    opening_amount = db.Column(db.Numeric(10, 2), nullable=False)
    expected_cash = db.Column(db.Numeric(10, 2), nullable=True)
    counted_cash = db.Column(db.Numeric(10, 2), nullable=True)
    note = db.Column(db.String(200), nullable=True)

    opened_by = db.relationship('User', foreign_keys=[opened_by_id])
    closed_by = db.relationship('User', foreign_keys=[closed_by_id])

    __table_args__ = (
        db.Index('uq_cash_one_open_per_tenant', 'tenant_id', unique=True,
                 postgresql_where=db.text('closed_at IS NULL'), sqlite_where=db.text('closed_at IS NULL')),
        db.Index('ix_cash_sessions_tenant_opened', 'tenant_id', 'opened_at'),
        db.CheckConstraint('opening_amount >= 0', name='ck_cash_opening_nonneg'),
    )

    @property
    def is_open(self):
        return self.closed_at is None

    @property
    def difference(self):
        """Contado - esperado. Positivo = sobra plata, negativo = falta."""
        if self.counted_cash is None or self.expected_cash is None:
            return None
        return self.counted_cash - self.expected_cash
