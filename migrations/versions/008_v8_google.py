"""v8: inicio de sesión con Google

Revision ID: 008v8google
Revises: 007v6catalog
Create Date: 2026-11-17 20:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '008v8google'
down_revision = '007v6catalog'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('google_sub', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_users_google_sub', 'users', ['google_sub'])


def downgrade():
    op.drop_constraint('uq_users_google_sub', 'users', type_='unique')
    op.drop_column('users', 'google_sub')
