import re

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from . import inventory_bp
from ...extensions import db
from ...models.product import DEFAULT_LOW_STOCK_THRESHOLD, Product
from ...models.stock_movement import REASON_INITIAL, REASON_LABELS, StockMovement
from ...services import pricing
from ...services.inventory import apply_movement, lock_products, register_manual_movement
from ...utils.decorators import login_required_with_tenant, require
from ...utils.permissions import (
    INVENTORY_MANAGE, INVENTORY_VIEW, REPORTS_VIEW, STOCK_ADJUST, STOCK_ENTRY)
from ...utils.pricing import APPLIES_TO, ROUNDING_OPTIONS
from ...utils.text import escape_like
from ...utils.validation import (
    ValidationFailure, clean_multiline, clean_text, parse_int, parse_money, parse_percent)

PER_PAGE = 25


def _own_product_or_404(product_id):
    return Product.query.filter_by(id=product_id, tenant_id=current_user.tenant_id).first_or_404()


def _product_form_data(form):
    """Valida el formulario y devuelve dict listo para el modelo (o levanta ValidationFailure)."""
    data = {
        'name': clean_text(form.get('name', ''), 'Nombre', max_len=200),
        'description': clean_multiline(form.get('description', ''), 'Descripción', max_len=2000) or None,
        'sku': clean_text(form.get('sku', ''), 'SKU', max_len=100, required=False) or None,
        'cost_price': parse_money(form.get('cost_price', ''), 'Precio de compra'),
        'sale_price': parse_money(form.get('sale_price', ''), 'Precio de venta'),
        'low_stock_threshold': parse_int(form.get('low_stock_threshold', DEFAULT_LOW_STOCK_THRESHOLD),
                                         'Alerta de stock bajo', minimum=0, maximum=100000),
    }
    return data


@inventory_bp.route('/productos')
@login_required_with_tenant
@require(INVENTORY_VIEW)
def product_list():
    q = request.args.get('q', '').strip()[:100]
    flt = request.args.get('filter', '')
    query = Product.query.filter_by(tenant_id=current_user.tenant_id)
    if flt == 'inactive':
        query = query.filter(Product.is_active.is_(False))
    else:
        query = query.filter(Product.is_active.is_(True))
        if flt == 'low':
            query = query.filter(Product.stock <= Product.low_stock_threshold)
    if q:
        like = f'%{escape_like(q)}%'
        query = query.filter(db.or_(Product.name.ilike(like, escape='\\'), Product.sku.ilike(like, escape='\\')))
    page = request.args.get('page', 1, type=int)
    products = query.order_by(Product.name).paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template('inventory/list.html', products=products, q=q, flt=flt)


@inventory_bp.route('/productos/nuevo', methods=['GET', 'POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def product_create():
    if request.method == 'POST':
        try:
            data = _product_form_data(request.form)
            initial = parse_int(request.form.get('stock', 0), 'Stock inicial', minimum=0)
            product = Product(tenant_id=current_user.tenant_id, stock=0, **data)
            db.session.add(product)
            db.session.flush()
            if initial:
                lock_products(current_user.tenant_id, [product.id])
                apply_movement(product, initial, REASON_INITIAL, user_id=current_user.id,
                               note='Stock inicial')
            db.session.commit()
            flash(f'Producto "{product.name}" creado.', 'success')
            return redirect(url_for('inventory.product_list'))
        except ValidationFailure as exc:
            db.session.rollback()
            flash(str(exc), 'danger')
        except IntegrityError:
            db.session.rollback()
            flash('Ya existe un producto con ese SKU.', 'danger')
        return render_template('inventory/form.html', product=None, form=request.form), 400
    return render_template('inventory/form.html', product=None, form={})


@inventory_bp.route('/productos/<int:product_id>/editar', methods=['GET', 'POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def product_edit(product_id):
    product = _own_product_or_404(product_id)
    if request.method == 'POST':
        try:
            for key, value in _product_form_data(request.form).items():
                setattr(product, key, value)
            db.session.commit()
            flash('Producto actualizado.', 'success')
            return redirect(url_for('inventory.product_list'))
        except ValidationFailure as exc:
            db.session.rollback()
            flash(str(exc), 'danger')
        except IntegrityError:
            db.session.rollback()
            flash('Ya existe otro producto con ese SKU.', 'danger')
        return render_template('inventory/form.html', product=product, form=request.form), 400
    return render_template('inventory/form.html', product=product, form={})


@inventory_bp.route('/productos/<int:product_id>/eliminar', methods=['POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def product_delete(product_id):
    product = _own_product_or_404(product_id)
    product.is_active = False
    db.session.commit()
    flash(f'"{product.name}" se desactivó. Las ventas anteriores se conservan.', 'info')
    return redirect(url_for('inventory.product_list'))


@inventory_bp.route('/productos/<int:product_id>/reactivar', methods=['POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def product_reactivate(product_id):
    product = _own_product_or_404(product_id)
    product.is_active = True
    db.session.commit()
    flash(f'"{product.name}" volvió a estar activo.', 'success')
    return redirect(url_for('inventory.product_list', filter='inactive'))


# ─── STOCK ──────────────────────────────────────────────────
@inventory_bp.route('/productos/<int:product_id>/stock')
@login_required_with_tenant
@require(STOCK_ENTRY)
def stock_form(product_id):
    product = _own_product_or_404(product_id)
    page = request.args.get('page', 1, type=int)
    movements = (StockMovement.query.filter_by(tenant_id=current_user.tenant_id, product_id=product.id)
                 .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
                 .paginate(page=page, per_page=PER_PAGE, error_out=False))
    return render_template('inventory/stock.html', product=product, movements=movements)


@inventory_bp.route('/productos/<int:product_id>/stock', methods=['POST'])
@login_required_with_tenant
@require(STOCK_ENTRY)
def stock_move(product_id):
    product = _own_product_or_404(product_id)
    kind = request.form.get('kind', '')
    # Los empleados solo reponen; mermas y ajustes (que pueden tapar faltantes) son del dueño.
    if kind in ('loss', 'adjust_set') and not current_user.can(STOCK_ADJUST):
        flash('Solo el dueño puede registrar mermas o ajustes.', 'danger')
        return redirect(url_for('inventory.stock_form', product_id=product.id))
    try:
        label = 'Stock contado' if kind == 'adjust_set' else 'Cantidad'
        qty = parse_int(request.form.get('quantity', ''), label, minimum=0 if kind == 'adjust_set' else 1)
        note = clean_text(request.form.get('note', ''), 'Nota', max_len=200, required=False)
        register_manual_movement(current_user.tenant_id, product.id, kind, qty, current_user.id, note)
        db.session.commit()
        flash('Movimiento registrado.', 'success')
    except ValidationFailure as exc:
        db.session.rollback()
        flash(str(exc), 'danger')
    return redirect(url_for('inventory.stock_form', product_id=product.id))


@inventory_bp.route('/movimientos')
@login_required_with_tenant
@require(REPORTS_VIEW)
def movement_list():
    reason = request.args.get('reason', '')
    query = (db.session.query(StockMovement, Product.name)
             .join(Product, db.and_(Product.id == StockMovement.product_id,
                                    Product.tenant_id == StockMovement.tenant_id))
             .filter(StockMovement.tenant_id == current_user.tenant_id))
    if reason in REASON_LABELS:
        query = query.filter(StockMovement.reason == reason)
    page = request.args.get('page', 1, type=int)
    rows = (query.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
            .paginate(page=page, per_page=PER_PAGE, error_out=False))
    return render_template('inventory/movements.html', rows=rows, reason=reason, reasons=REASON_LABELS)


# ─── ACTUALIZACIÓN MASIVA DE PRECIOS ────────────────────────
_UUID_RE = re.compile(r'^[0-9a-f-]{36}$')


def _price_form(form):
    """Lee y valida el formulario de precios. Devuelve dict con valores ya limpios."""
    percent = parse_percent(form.get('percent', ''))
    percent = abs(percent) if form.get('direction', 'up') == 'up' else -abs(percent)
    if percent < -90:
        raise ValidationFailure('No se puede bajar más de un 90%.')
    applies_to = form.get('applies_to', 'sale')
    rounding = form.get('rounding', 'none')
    if applies_to not in APPLIES_TO:
        raise ValidationFailure('Elegí qué precio actualizar.')
    if rounding not in ROUNDING_OPTIONS:
        raise ValidationFailure('Redondeo inválido.')
    search = clean_text(form.get('search', ''), 'La búsqueda', max_len=100, required=False) or ''
    scope = form.get('scope', 'all')
    if scope == 'search' and not search:
        raise ValidationFailure('Escribí qué productos querés actualizar (por ejemplo "yerba").')
    if scope != 'search':
        search = ''
    return {'percent': percent, 'applies_to': applies_to, 'rounding': rounding, 'search': search, 'scope': scope}


@inventory_bp.route('/precios')
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def price_update():
    return render_template('inventory/prices.html', form={}, applies=APPLIES_TO, roundings=ROUNDING_OPTIONS,
                           batches=pricing.list_batches(current_user.tenant_id))


@inventory_bp.route('/precios/vista-previa', methods=['POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def price_preview():
    try:
        data = _price_form(request.form)
        rows, unchanged = pricing.build_preview(current_user.tenant_id, data['percent'], data['applies_to'],
                                                data['rounding'], data['search'])
        if not rows:
            raise ValidationFailure('Ningún producto cambiaría de precio con esos valores.')
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
        return render_template('inventory/prices.html', form=request.form, applies=APPLIES_TO,
                               roundings=ROUNDING_OPTIONS,
                               batches=pricing.list_batches(current_user.tenant_id)), 400
    return render_template('inventory/prices_preview.html', rows=rows[:100], total=len(rows), unchanged=unchanged,
                           data=data, applies=APPLIES_TO, roundings=ROUNDING_OPTIONS)


@inventory_bp.route('/precios/aplicar', methods=['POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def price_apply():
    try:
        data = _price_form(request.form)
        _, count = pricing.apply_update(current_user.tenant_id, current_user.id, data['percent'],
                                        data['applies_to'], data['rounding'], data['search'])
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('inventory.price_update'))
    flash(f'Listo: se actualizaron los precios de {count} producto{"s" if count != 1 else ""}. '
          'Si te equivocaste, podés revertirlo desde el historial.', 'success')
    return redirect(url_for('inventory.price_update'))


@inventory_bp.route('/precios/revertir/<batch_id>', methods=['POST'])
@login_required_with_tenant
@require(INVENTORY_MANAGE)
def price_revert(batch_id):
    if not _UUID_RE.match(batch_id):
        flash('Operación inválida.', 'danger')
        return redirect(url_for('inventory.price_update'))
    try:
        restored, skipped = pricing.revert_batch(current_user.tenant_id, current_user.id, batch_id)
        extra = f' ({skipped} no se tocaron porque su precio cambió después)' if skipped else ''
        flash(f'Se restauraron los precios anteriores de {restored} producto{"s" if restored != 1 else ""}{extra}.', 'success')
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('inventory.price_update'))
