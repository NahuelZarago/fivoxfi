"""v3: movimientos de stock, rol cliente, anulación de ventas, restricciones de integridad

Revision ID: 004v3movements
Revises: 003v2schema
Create Date: 2026-11-16 00:00:00

Específica de PostgreSQL (usa SQL propio para rellenar códigos).
Es segura sobre datos existentes: corrige valores negativos antes de agregar CHECK,
y crea un movimiento "stock inicial" por cada producto con stock para que el libro cuadre.
"""
from alembic import op
import sqlalchemy as sa

revision = '004v3movements'
down_revision = '003v2schema'
branch_labels = None
depends_on = None


def upgrade():
    # ── users: versión de sesión + rol renombrado ─────────────
    op.add_column('users', sa.Column('auth_version', sa.Integer(), nullable=False, server_default='0'))
    op.execute("UPDATE users SET role = 'employee' WHERE role = 'seller'")

    # ── tenants: código de clientes ───────────────────────────
    op.add_column('tenants', sa.Column('client_code', sa.String(length=20), nullable=True))
    op.execute("""
        UPDATE tenants
        SET client_code = 'FC-' || UPPER(SUBSTRING(MD5(RANDOM()::TEXT || id::TEXT), 1, 6))
        WHERE client_code IS NULL
    """)
    op.alter_column('tenants', 'client_code', nullable=False)
    op.create_unique_constraint('uq_tenants_client_code', 'tenants', ['client_code'])
    op.alter_column('tenants', 'plan', existing_type=sa.String(length=50), nullable=False, server_default='basic')
    op.execute("UPDATE tenants SET plan = 'basic' WHERE plan IS NULL")

    # ── products ──────────────────────────────────────────────
    op.add_column('products', sa.Column('low_stock_threshold', sa.Integer(), nullable=False, server_default='5'))
    op.execute("UPDATE products SET is_active = TRUE WHERE is_active IS NULL")
    op.alter_column('products', 'is_active', existing_type=sa.Boolean(), nullable=False)
    # Datos viejos inválidos se corrigen antes de exigir las reglas.
    op.execute("UPDATE products SET stock = 0 WHERE stock < 0")
    op.execute("UPDATE products SET cost_price = 0 WHERE cost_price < 0")
    op.execute("UPDATE products SET sale_price = 0 WHERE sale_price < 0")
    op.create_check_constraint('ck_products_stock_nonneg', 'products', 'stock >= 0')
    op.create_check_constraint('ck_products_prices_nonneg', 'products', 'cost_price >= 0 AND sale_price >= 0')
    op.create_unique_constraint('uq_products_tenant_id_id', 'products', ['tenant_id', 'id'])

    # ── sales: anulación ──────────────────────────────────────
    op.add_column('sales', sa.Column('voided_at', sa.DateTime(), nullable=True))
    op.add_column('sales', sa.Column('voided_by_id', sa.Integer(), nullable=True))
    op.add_column('sales', sa.Column('void_reason', sa.String(length=200), nullable=True))
    op.create_foreign_key('fk_sales_voided_by', 'sales', 'users', ['voided_by_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_sales_tenant_created', 'sales', ['tenant_id', 'created_at'])
    op.create_check_constraint('ck_sale_items_qty_pos', 'sale_items', 'quantity > 0')

    # ── stock_movements ───────────────────────────────────────
    op.create_table(
        'stock_movements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('sale_id', sa.Integer(), sa.ForeignKey('sales.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reason', sa.String(length=20), nullable=False),
        sa.Column('quantity_change', sa.Integer(), nullable=False),
        sa.Column('stock_after', sa.Integer(), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id', 'product_id'], ['products.tenant_id', 'products.id'],
                                name='fk_movements_tenant_product', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_movements_tenant', ondelete='CASCADE'),
        sa.CheckConstraint('quantity_change <> 0', name='ck_movements_nonzero'),
        sa.CheckConstraint('stock_after >= 0', name='ck_movements_stock_after_nonneg'),
    )
    op.create_index('ix_stock_movements_tenant_id', 'stock_movements', ['tenant_id'])
    op.create_index('ix_stock_movements_product_id', 'stock_movements', ['product_id'])
    op.create_index('ix_stock_movements_sale_id', 'stock_movements', ['sale_id'])
    op.create_index('ix_movements_tenant_created', 'stock_movements', ['tenant_id', 'created_at'])

    # El stock que ya existía queda registrado como "stock inicial".
    op.execute("""
        INSERT INTO stock_movements (tenant_id, product_id, reason, quantity_change, stock_after, note, created_at)
        SELECT tenant_id, id, 'initial', stock, stock, 'Stock previo a la migración', NOW()
        FROM products WHERE stock > 0
    """)


def downgrade():
    op.drop_table('stock_movements')
    op.drop_constraint('ck_sale_items_qty_pos', 'sale_items', type_='check')
    op.drop_index('ix_sales_tenant_created', table_name='sales')
    op.drop_constraint('fk_sales_voided_by', 'sales', type_='foreignkey')
    op.drop_column('sales', 'void_reason')
    op.drop_column('sales', 'voided_by_id')
    op.drop_column('sales', 'voided_at')
    op.drop_constraint('uq_products_tenant_id_id', 'products', type_='unique')
    op.drop_constraint('ck_products_prices_nonneg', 'products', type_='check')
    op.drop_constraint('ck_products_stock_nonneg', 'products', type_='check')
    op.drop_column('products', 'low_stock_threshold')
    op.drop_constraint('uq_tenants_client_code', 'tenants', type_='unique')
    op.drop_column('tenants', 'client_code')
    op.execute("UPDATE users SET role = 'seller' WHERE role = 'employee'")
    op.drop_column('users', 'auth_version')
