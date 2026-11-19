"""v9: aceptación de Términos y Condiciones

Revision ID: 009v9terms
Revises: 008v8google
Create Date: 2026-11-18 21:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '009v9terms'
down_revision = '008v8google'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('terms_accepted_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('terms_version', sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column('users', 'terms_version')
    op.drop_column('users', 'terms_accepted_at')
