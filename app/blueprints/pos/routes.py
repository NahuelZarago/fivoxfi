from flask import jsonify, render_template, request
from flask_login import current_user

from . import pos_bp
from ...extensions import db
from ...models.product import Product
from ...services.sales import create_sale
from ...utils.decorators import login_required_with_tenant, require
from ...utils.formatting import format_money
from ...utils.permissions import POS_SELL
from ...utils.text import escape_like
from ...utils.validation import ValidationFailure

GRID_LIMIT = 200
SELLABLE_METHODS = [('cash', 'Efectivo'), ('card', 'Tarjeta'), ('transfer', 'Transferencia')]


def _product_json(p):
    # El precio viaja como texto con 2 decimales: el navegador solo lo muestra;
    # el servidor SIEMPRE recalcula el total con los precios de la base.
    return {'id': p.id, 'name': p.name, 'sku': p.sku or '', 'price': f'{p.sale_price:.2f}', 'stock': p.stock}


@pos_bp.route('/terminal')
@login_required_with_tenant
@require(POS_SELL)
def terminal():
    products = (Product.query.filter(Product.tenant_id == current_user.tenant_id,
                                     Product.is_active.is_(True), Product.stock > 0)
                .order_by(Product.name).limit(GRID_LIMIT).all())
    return render_template('pos/terminal.html', products=[_product_json(p) for p in products],
                           methods=SELLABLE_METHODS)


@pos_bp.route('/api/products/search')
@login_required_with_tenant
@require(POS_SELL)
def search_products():
    q = request.args.get('q', '').strip()[:100]
    if not q:
        return jsonify([])
    like = f'%{escape_like(q)}%'
    products = (Product.query.filter(
        Product.tenant_id == current_user.tenant_id, Product.is_active.is_(True), Product.stock > 0,
        db.or_(Product.name.ilike(like, escape='\\'), Product.sku.ilike(like, escape='\\')))
        .order_by(Product.name).limit(10).all())
    return jsonify([_product_json(p) for p in products])


@pos_bp.route('/api/sale', methods=['POST'])
@login_required_with_tenant
@require(POS_SELL)
def process_sale():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Solicitud inválida.'}), 400
    try:
        sale = create_sale(current_user.tenant_id, current_user.id, data.get('items'),
                           payment_method=data.get('payment_method', 'cash'))
    except ValidationFailure as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'success': True, 'sale_id': sale.id, 'total': format_money(sale.total_amount),
                    'message': f'Venta #{sale.id} registrada: {format_money(sale.total_amount)}.'})
