from flask import abort, flash, redirect, render_template, request, url_for

from flask_login import current_user

from . import catalog_bp
from ...services import catalog as svc
from ...utils.decorators import login_required_with_tenant, require
from ...utils.permissions import INVENTORY_MANAGE
from ...utils.validation import ValidationFailure, clean_text, validate_email


# ─── CATEGORÍAS ─────────────────────────────────────────────
@catalog_bp.route('/categorias')
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def categories():
    return render_template('catalog/categories.html', rows=svc.category_rows(current_user.tenant_id))


@catalog_bp.route('/categorias/crear', methods=['POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def category_create():
    try:
        name = clean_text(request.form.get('name', ''), 'El nombre', max_len=80)
        svc.create_category(current_user.tenant_id, name)
        flash(f'Categoría "{name}" creada.', 'success')
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('catalog.categories'))


@catalog_bp.route('/categorias/<int:category_id>/renombrar', methods=['POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def category_rename(category_id):
    try:
        name = clean_text(request.form.get('name', ''), 'El nombre', max_len=80)
        svc.rename_category(current_user.tenant_id, category_id, name)
        flash('Categoría renombrada.', 'success')
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('catalog.categories'))


@catalog_bp.route('/categorias/<int:category_id>/eliminar', methods=['POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def category_delete(category_id):
    try:
        n = svc.delete_category(current_user.tenant_id, category_id)
        flash(f'Categoría eliminada. {n} producto{"s" if n != 1 else ""} quedó sin categoría.', 'info')
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('catalog.categories'))


# ─── PROVEEDORES ────────────────────────────────────────────
def _supplier_form(form):
    return {
        'name': clean_text(form.get('name', ''), 'El nombre', max_len=120),
        'phone': clean_text(form.get('phone', ''), 'El teléfono', max_len=40, required=False) or None,
        'email': (validate_email(form.get('email', '')) if form.get('email', '').strip() else None),
        'notes': clean_text(form.get('notes', ''), 'Las notas', max_len=500, required=False) or None,
    }


@catalog_bp.route('/proveedores')
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def suppliers():
    return render_template('catalog/suppliers.html', rows=svc.supplier_rows(current_user.tenant_id))


@catalog_bp.route('/proveedores/nuevo', methods=['GET', 'POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def supplier_create():
    if request.method == 'POST':
        try:
            sup = svc.save_supplier(current_user.tenant_id, _supplier_form(request.form))
            flash(f'Proveedor "{sup.name}" creado.', 'success')
            return redirect(url_for('catalog.suppliers'))
        except ValidationFailure as exc:
            flash(str(exc), 'danger')
        return render_template('catalog/supplier_form.html', supplier=None, form=request.form), 400
    return render_template('catalog/supplier_form.html', supplier=None, form={})


@catalog_bp.route('/proveedores/<int:supplier_id>/editar', methods=['GET', 'POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def supplier_edit(supplier_id):
    try:
        supplier = svc.get_supplier(current_user.tenant_id, supplier_id)
    except ValidationFailure:
        abort(404)
    if request.method == 'POST':
        try:
            svc.save_supplier(current_user.tenant_id, _supplier_form(request.form), supplier_id=supplier.id)
            flash('Proveedor actualizado.', 'success')
            return redirect(url_for('catalog.suppliers'))
        except ValidationFailure as exc:
            flash(str(exc), 'danger')
        return render_template('catalog/supplier_form.html', supplier=supplier, form=request.form), 400
    return render_template('catalog/supplier_form.html', supplier=supplier, form={})


@catalog_bp.route('/proveedores/<int:supplier_id>/eliminar', methods=['POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def supplier_delete(supplier_id):
    try:
        n = svc.delete_supplier(current_user.tenant_id, supplier_id)
        flash(f'Proveedor eliminado. {n} producto{"s" if n != 1 else ""} quedó sin proveedor.', 'info')
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('catalog.suppliers'))
