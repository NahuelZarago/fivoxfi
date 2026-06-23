from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user
from . import inventory_bp
from ...extensions import db
from ...models.product import Product
from ...utils.decorators import login_required_with_tenant, admin_required


@inventory_bp.route('/productos')
@login_required_with_tenant
@admin_required
def product_list():
    products = Product.query.filter_by(tenant_id=current_user.tenant_id).order_by(Product.name).all()
    return render_template('inventory/list.html', products=products)


@inventory_bp.route('/productos/nuevo', methods=['GET', 'POST'])
@login_required_with_tenant
@admin_required
def product_create():
    if request.method == 'POST':
        sku = request.form.get('sku', '').strip() or None
        if sku and Product.query.filter_by(tenant_id=current_user.tenant_id, sku=sku).first():
            flash('Ya existe un producto con ese SKU.', 'danger')
            return render_template('inventory/form.html', product=None)
        product = Product(
            tenant_id=current_user.tenant_id,
            name=request.form.get('name', '').strip(),
            description=request.form.get('description', '').strip(),
            sku=sku,
            cost_price=float(request.form.get('cost_price', 0)),
            sale_price=float(request.form.get('sale_price', 0)),
            stock=int(request.form.get('stock', 0)),
        )
        db.session.add(product)
        db.session.commit()
        flash(f'Producto "{product.name}" creado.', 'success')
        return redirect(url_for('inventory.product_list'))
    return render_template('inventory/form.html', product=None)


@inventory_bp.route('/productos/<int:product_id>/editar', methods=['GET', 'POST'])
@login_required_with_tenant
@admin_required
def product_edit(product_id):
    product = Product.query.filter_by(id=product_id, tenant_id=current_user.tenant_id).first_or_404()
    if request.method == 'POST':
        product.name = request.form.get('name', '').strip()
        product.description = request.form.get('description', '').strip()
        product.sku = request.form.get('sku', '').strip() or None
        product.cost_price = float(request.form.get('cost_price', 0))
        product.sale_price = float(request.form.get('sale_price', 0))
        product.stock = int(request.form.get('stock', 0))
        db.session.commit()
        flash(f'Producto actualizado.', 'success')
        return redirect(url_for('inventory.product_list'))
    return render_template('inventory/form.html', product=product)


@inventory_bp.route('/productos/<int:product_id>/eliminar', methods=['POST'])
@login_required_with_tenant
@admin_required
def product_delete(product_id):
    product = Product.query.filter_by(id=product_id, tenant_id=current_user.tenant_id).first_or_404()
    product.is_active = False
    db.session.commit()
    flash(f'Producto desactivado.', 'info')
    return redirect(url_for('inventory.product_list'))
