"""v5: caja diaria (apertura y cierre)

Revision ID: 006v5cash
Revises: 005v4pricesadmin
Create Date: 2026-11-17 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '006v5cash'
down_revision = '005v4pricesadmin'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'cash_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('opened_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('closed_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('opened_at', sa.DateTime(), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('opening_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('expected_cash', sa.Numeric(10, 2), nullable=True),
        sa.Column('counted_cash', sa.Numeric(10, 2), nullable=True),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.CheckConstraint('opening_amount >= 0', name='ck_cash_opening_nonneg'),
    )
    op.create_index('ix_cash_sessions_tenant_id', 'cash_sessions', ['tenant_id'])
    op.create_index('ix_cash_sessions_tenant_opened', 'cash_sessions', ['tenant_id', 'opened_at'])
    op.create_index('uq_cash_one_open_per_tenant', 'cash_sessions', ['tenant_id'], unique=True,
                    postgresql_where=sa.text('closed_at IS NULL'))


def downgrade():
    op.drop_table('cash_sessions')
