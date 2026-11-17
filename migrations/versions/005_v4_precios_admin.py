"""v4: historial de actualización de precios y administrador de plataforma

Revision ID: 005v4pricesadmin
Revises: 004v3movements
Create Date: 2026-11-17 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '005v4pricesadmin'
down_revision = '004v3movements'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('is_superadmin', sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        'price_changes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('batch_id', sa.String(length=36), nullable=False),
        sa.Column('percent', sa.Numeric(7, 2), nullable=False),
        sa.Column('applies_to', sa.String(length=10), nullable=False),
        sa.Column('old_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('new_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('old_sale', sa.Numeric(10, 2), nullable=False),
        sa.Column('new_sale', sa.Numeric(10, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('reverted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id', 'product_id'], ['products.tenant_id', 'products.id'],
                                name='fk_price_changes_tenant_product', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_price_changes_tenant', ondelete='CASCADE'),
    )
    op.create_index('ix_price_changes_tenant_id', 'price_changes', ['tenant_id'])
    op.create_index('ix_price_changes_product_id', 'price_changes', ['product_id'])
    op.create_index('ix_price_changes_batch_id', 'price_changes', ['batch_id'])
    op.create_index('ix_price_changes_tenant_created', 'price_changes', ['tenant_id', 'created_at'])


def downgrade():
    op.drop_table('price_changes')
    op.drop_column('users', 'is_superadmin')
