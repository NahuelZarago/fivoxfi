"""v2 schema: employee_code, is_email_confirmed, nullable tenant_id, role owner/seller

Revision ID: 003v2schema
Revises: cf5cd691217a
Create Date: 2026-06-22 00:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = '003v2schema'
down_revision = 'cf5cd691217a'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Agregar employee_code a tenants
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'employee_code',
            sa.String(length=20),
            nullable=True  # primero nullable para no romper filas existentes
        ))

    # 2. Rellenar employee_code en tenants existentes
    op.execute("""
        UPDATE tenants
        SET employee_code = 'FX-' || UPPER(SUBSTRING(MD5(RANDOM()::TEXT), 1, 6))
        WHERE employee_code IS NULL
    """)

    # 3. Hacer employee_code NOT NULL y UNIQUE
    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.alter_column('employee_code', nullable=False)
        batch_op.create_unique_constraint('uq_tenants_employee_code', ['employee_code'])

    # 4. Renombrar is_confirmed → is_email_confirmed en users
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'is_confirmed',
            new_column_name='is_email_confirmed',
            existing_type=sa.Boolean(),
            existing_nullable=False
        )

    # 5. Hacer tenant_id nullable en users (para usuarios sin rol asignado aún)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'tenant_id',
            existing_type=sa.Integer(),
            nullable=True
        )

    # 6. Eliminar unique constraint viejo de email por tenant (ahora email es único globalmente)
    with op.batch_alter_table('users', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('uq_user_email_per_tenant', type_='unique')
        except Exception:
            pass  # Si no existe, ignorar

    # 7. Eliminar usuarios duplicados (quedar solo con el más reciente por email)
    op.execute("""
        DELETE FROM users
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM users
            GROUP BY email
        )
    """)

    # 8. Agregar unique constraint global en email
    with op.batch_alter_table('users', schema=None) as batch_op:
        try:
            batch_op.create_unique_constraint('uq_users_email', ['email'])
        except Exception:
            pass

    # 9. Hacer role nullable (puede ser NULL mientras el usuario elige)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column(
            'role',
            existing_type=sa.String(length=20),
            nullable=True
        )


def downgrade():
    # Revertir: owner → admin
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'owner'")

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('role', existing_type=sa.String(20), nullable=False)
        batch_op.alter_column('tenant_id', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column(
            'is_email_confirmed',
            new_column_name='is_confirmed',
            existing_type=sa.Boolean(),
            existing_nullable=False
        )

    with op.batch_alter_table('tenants', schema=None) as batch_op:
        batch_op.drop_constraint('uq_tenants_employee_code', type_='unique')
        batch_op.drop_column('employee_code')