from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user
from datetime import datetime, timedelta
from sqlalchemy import func, desc

from . import dashboard_bp
from ...extensions import db
from ...utils.decorators import login_required_with_tenant, owner_required
from ...models.product import Product, LOW_STOCK_THRESHOLD
from ...models.sale import Sale, SaleItem
from ...models.user import User


@dashboard_bp.route('/')
@login_required_with_tenant
def index():
    owned_apps = [{'name': 'Sistema de Gestión', 'description': 'Inventario, ventas y reportes.', 'icon': '🏪'}]
    explore_apps = [
        {'name': 'Módulo de Reservas', 'description': 'Turnos y agenda online.', 'icon': '📅'},
        {'name': 'Tienda Online', 'description': 'Vendé tus productos por internet.', 'icon': '🛒'},
    ]
    return render_template('dashboard/index.html', owned_apps=owned_apps, explore_apps=explore_apps)


@dashboard_bp.route('/gestion')
@login_required_with_tenant
def gestion():
    tid = current_user.tenant_id
    today = datetime.utcnow()

    weekly_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        ds = day.replace(hour=0, minute=0, second=0, microsecond=0)
        de = day.replace(hour=23, minute=59, second=59)
        total = db.session.query(func.sum(Sale.total_amount)).filter(
            Sale.tenant_id == tid, Sale.created_at >= ds, Sale.created_at <= de
        ).scalar() or 0
        weekly_data.append({'day': day.strftime('%a'), 'total': float(total)})

    top_products = db.session.query(
        SaleItem.product_name,
        func.sum(SaleItem.quantity).label('total_qty'),
        func.sum(SaleItem.quantity * SaleItem.unit_sale_price).label('total_revenue')
    ).join(Sale).filter(Sale.tenant_id == tid).group_by(
        SaleItem.product_name).order_by(desc('total_qty')).limit(5).all()

    low_stock = Product.query.filter(
        Product.tenant_id == tid, Product.is_active == True,
        Product.stock <= LOW_STOCK_THRESHOLD
    ).order_by(Product.stock).all()

    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.tenant_id == tid, Sale.created_at >= today_start).scalar() or 0
    today_profit = db.session.query(func.sum(Sale.total_amount - Sale.total_cost)).filter(
        Sale.tenant_id == tid, Sale.created_at >= today_start).scalar() or 0
    month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.tenant_id == tid, Sale.created_at >= month_start).scalar() or 0
    today_count = db.session.query(func.count(Sale.id)).filter(
        Sale.tenant_id == tid, Sale.created_at >= today_start).scalar() or 0

    return render_template('dashboard/gestion.html',
        weekly_data=weekly_data, top_products=top_products,
        low_stock=low_stock, today_sales=float(today_sales),
        today_profit=float(today_profit), month_sales=float(month_sales),
        today_count=int(today_count))


@dashboard_bp.route('/configuracion')
@login_required_with_tenant
def settings():
    return render_template('dashboard/settings.html')


@dashboard_bp.route('/configuracion/actualizar', methods=['POST'])
@login_required_with_tenant
def settings_update():
    action = request.form.get('action')
    if action == 'profile':
        current_user.username = request.form.get('username', '').strip()
        current_user.email = request.form.get('email', '').strip().lower()
        db.session.commit()
        flash('Datos actualizados.', 'success')
    elif action == 'password':
        cur = request.form.get('current_password', '')
        new = request.form.get('new_password', '')
        if not current_user.check_password(cur):
            flash('Contraseña actual incorrecta.', 'danger')
        elif len(new) < 8:
            flash('La nueva contraseña debe tener al menos 8 caracteres.', 'danger')
        else:
            current_user.set_password(new)
            db.session.commit()
            flash('Contraseña cambiada.', 'success')
    elif action == 'business' and current_user.is_owner:
        current_user.tenant.name = request.form.get('business_name', '').strip()
        db.session.commit()
        flash('Datos del negocio actualizados.', 'success')
    return redirect(url_for('dashboard.settings'))


@dashboard_bp.route('/empleados')
@login_required_with_tenant
@owner_required
def employees():
    all_employees = User.query.filter_by(tenant_id=current_user.tenant_id).order_by(User.created_at).all()
    return render_template('dashboard/employees.html', employees=all_employees)


@dashboard_bp.route('/empleados/crear', methods=['POST'])
@login_required_with_tenant
@owner_required
def employee_create():
    email = request.form.get('email', '').strip().lower()
    if User.query.filter_by(email=email).first():
        flash('Ya existe un usuario con ese email.', 'danger')
        return redirect(url_for('dashboard.employees'))

    new_user = User(
        tenant_id=current_user.tenant_id,
        username=request.form.get('username', '').strip(),
        email=email,
        role='seller',
        is_email_confirmed=True,
        is_active=True,
    )
    new_user.set_password(request.form.get('password', ''))
    db.session.add(new_user)
    db.session.commit()
    flash(f'Empleado "{new_user.username}" creado correctamente.', 'success')
    return redirect(url_for('dashboard.employees'))


@dashboard_bp.route('/empleados/<int:user_id>/toggle', methods=['POST'])
@login_required_with_tenant
@owner_required
def employee_toggle(user_id):
    if user_id == current_user.id:
        flash('No podés desactivar tu propia cuenta.', 'warning')
        return redirect(url_for('dashboard.employees'))
    user = User.query.filter_by(id=user_id, tenant_id=current_user.tenant_id).first_or_404()
    if user.is_owner:
        flash('No podés modificar la cuenta de otro dueño.', 'danger')
        return redirect(url_for('dashboard.employees'))
    user.is_active = not user.is_active
    db.session.commit()
    flash(f'"{user.username}" {"activado" if user.is_active else "dado de baja"}.', 'success')
    return redirect(url_for('dashboard.employees'))
