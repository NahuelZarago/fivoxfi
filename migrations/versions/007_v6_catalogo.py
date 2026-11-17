"""v6: categorías y proveedores

Revision ID: 007v6catalog
Revises: 006v5cash
Create Date: 2026-11-17 18:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = '007v6catalog'
down_revision = '006v5cash'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_category_name_per_tenant'),
        sa.UniqueConstraint('tenant_id', 'id', name='uq_categories_tenant_id_id'),
    )
    op.create_index('ix_categories_tenant_id', 'categories', ['tenant_id'])
    op.create_table(
        'suppliers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_supplier_name_per_tenant'),
        sa.UniqueConstraint('tenant_id', 'id', name='uq_suppliers_tenant_id_id'),
    )
    op.create_index('ix_suppliers_tenant_id', 'suppliers', ['tenant_id'])

    op.add_column('products', sa.Column('category_id', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('supplier_id', sa.Integer(), nullable=True))
    op.create_index('ix_products_category_id', 'products', ['category_id'])
    op.create_index('ix_products_supplier_id', 'products', ['supplier_id'])
    op.create_foreign_key('fk_products_tenant_category', 'products', 'categories',
                          ['tenant_id', 'category_id'], ['tenant_id', 'id'])
    op.create_foreign_key('fk_products_tenant_supplier', 'products', 'suppliers',
                          ['tenant_id', 'supplier_id'], ['tenant_id', 'id'])


def downgrade():
    op.drop_constraint('fk_products_tenant_supplier', 'products', type_='foreignkey')
    op.drop_constraint('fk_products_tenant_category', 'products', type_='foreignkey')
    op.drop_index('ix_products_supplier_id', table_name='products')
    op.drop_index('ix_products_category_id', table_name='products')
    op.drop_column('products', 'supplier_id')
    op.drop_column('products', 'category_id')
    op.drop_table('suppliers')
    op.drop_table('categories')
