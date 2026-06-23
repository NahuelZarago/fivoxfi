from flask import render_template, request, jsonify
from flask_login import current_user
from . import pos_bp
from ...extensions import db
from ...models.product import Product
from ...models.sale import Sale, SaleItem
from ...utils.decorators import login_required_with_tenant, seller_or_owner_required as seller_or_admin_required


@pos_bp.route('/terminal')
@login_required_with_tenant
@seller_or_admin_required
def terminal():
    products = Product.query.filter_by(
        tenant_id=current_user.tenant_id,
        is_active=True
    ).filter(Product.stock > 0).order_by(Product.name).all()
    return render_template('pos/terminal.html', products=products)


@pos_bp.route('/api/products/search')
@login_required_with_tenant
@seller_or_admin_required
def search_products():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    products = Product.query.filter(
        Product.tenant_id == current_user.tenant_id,
        Product.is_active == True,
        Product.stock > 0,
        db.or_(Product.name.ilike(f'%{q}%'), Product.sku.ilike(f'%{q}%'))
    ).limit(10).all()
    return jsonify([p.to_dict() for p in products])


@pos_bp.route('/api/sale', methods=['POST'])
@login_required_with_tenant
@seller_or_admin_required
def process_sale():
    data = request.get_json()
    if not data or not data.get('items'):
        return jsonify({'error': 'No se recibieron productos.'}), 400

    payment_method = data.get('payment_method', 'cash')
    total_amount = 0.0
    total_cost = 0.0
    sale_items = []

    for item in data.get('items', []):
        product = Product.query.filter_by(
            id=item['product_id'], tenant_id=current_user.tenant_id, is_active=True
        ).first()
        if not product:
            return jsonify({'error': f'Producto ID {item["product_id"]} no encontrado.'}), 404
        qty = int(item['quantity'])
        if qty <= 0:
            return jsonify({'error': 'La cantidad debe ser mayor a cero.'}), 400
        if product.stock < qty:
            return jsonify({'error': f'Stock insuficiente para "{product.name}". Disponible: {product.stock}'}), 400

        subtotal = float(product.sale_price) * qty
        cost = float(product.cost_price) * qty
        total_amount += subtotal
        total_cost += cost
        sale_items.append(SaleItem(
            product_id=product.id, product_name=product.name, quantity=qty,
            unit_sale_price=product.sale_price, unit_cost_price=product.cost_price,
        ))
        product.stock -= qty

    sale = Sale(
        tenant_id=current_user.tenant_id, seller_id=current_user.id,
        total_amount=total_amount, total_cost=total_cost,
        payment_method=payment_method, items=sale_items
    )
    db.session.add(sale)
    db.session.commit()
    return jsonify({'success': True, 'sale_id': sale.id, 'total': total_amount,
                    'message': f'Venta #{sale.id} registrada correctamente.'})
