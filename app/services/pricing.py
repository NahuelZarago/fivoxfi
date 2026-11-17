"""Actualización masiva de precios: vista previa, aplicación, historial y reversión."""
import uuid
from datetime import datetime
from decimal import Decimal

from ..extensions import db
from ..models.price_change import PriceChange
from ..models.product import Product
from ..utils.pricing import APPLIES_TO, ROUNDING_OPTIONS, compute_new_price
from ..utils.text import escape_like
from ..utils.validation import ValidationFailure

MAX_PRODUCTS_PER_UPDATE = 5000


def _scoped_query(tenant_id, search):
    q = Product.query.filter(Product.tenant_id == tenant_id, Product.is_active.is_(True))
    if search:
        like = f'%{escape_like(search)}%'
        q = q.filter(db.or_(Product.name.ilike(like, escape='\\'), Product.sku.ilike(like, escape='\\')))
    return q


def _validate_options(applies_to, rounding):
    if applies_to not in APPLIES_TO:
        raise ValidationFailure('Elegí qué precio actualizar.')
    if rounding not in ROUNDING_OPTIONS:
        raise ValidationFailure('Redondeo inválido.')
    return ROUNDING_OPTIONS[rounding][0]


def _new_prices(product, percent, applies_to, step):
    cost = compute_new_price(product.cost_price, percent, step) if applies_to in ('cost', 'both') else product.cost_price
    sale = compute_new_price(product.sale_price, percent, step) if applies_to in ('sale', 'both') else product.sale_price
    return cost, sale


def build_preview(tenant_id, percent, applies_to, rounding, search=None):
    """Calcula (sin guardar) cómo quedarían los precios. Devuelve (filas, total_afectados, sin_cambio)."""
    step = _validate_options(applies_to, rounding)
    products = _scoped_query(tenant_id, search).order_by(Product.name).limit(MAX_PRODUCTS_PER_UPDATE + 1).all()
    if len(products) > MAX_PRODUCTS_PER_UPDATE:
        raise ValidationFailure(f'Son más de {MAX_PRODUCTS_PER_UPDATE} productos: acotá con una búsqueda.')
    rows, unchanged = [], 0
    for p in products:
        new_cost, new_sale = _new_prices(p, percent, applies_to, step)
        if new_cost == p.cost_price and new_sale == p.sale_price:
            unchanged += 1
            continue
        rows.append({'id': p.id, 'name': p.name, 'old_cost': p.cost_price, 'new_cost': new_cost,
                     'old_sale': p.sale_price, 'new_sale': new_sale})
    return rows, unchanged


def apply_update(tenant_id, user_id, percent, applies_to, rounding, search=None):
    """
    Aplica el cambio. Vuelve a calcular todo con los precios ACTUALES (bloqueando las filas),
    así lo que se guarda nunca depende de lo que mostró la vista previa. Devuelve (batch_id, cantidad).
    """
    step = _validate_options(applies_to, rounding)
    try:
        ids = [r[0] for r in _scoped_query(tenant_id, search).with_entities(Product.id).limit(MAX_PRODUCTS_PER_UPDATE + 1).all()]
        if len(ids) > MAX_PRODUCTS_PER_UPDATE:
            raise ValidationFailure(f'Son más de {MAX_PRODUCTS_PER_UPDATE} productos: acotá con una búsqueda.')
        products = (Product.query.filter(Product.tenant_id == tenant_id, Product.id.in_(sorted(ids)))
                    .order_by(Product.id).with_for_update().all()) if ids else []
        batch_id, changed = str(uuid.uuid4()), 0
        for p in products:
            new_cost, new_sale = _new_prices(p, percent, applies_to, step)
            if new_cost == p.cost_price and new_sale == p.sale_price:
                continue
            db.session.add(PriceChange(
                tenant_id=tenant_id, product_id=p.id, user_id=user_id, batch_id=batch_id,
                percent=percent, applies_to=applies_to,
                old_cost=p.cost_price, new_cost=new_cost, old_sale=p.sale_price, new_sale=new_sale))
            p.cost_price, p.sale_price = new_cost, new_sale
            changed += 1
        if not changed:
            raise ValidationFailure('Ningún precio cambiaría con esos valores.')
        db.session.commit()
        return batch_id, changed
    except Exception:
        db.session.rollback()
        raise


def list_batches(tenant_id, limit=30):
    """Últimas operaciones, agrupadas por batch."""
    rows = (db.session.query(
        PriceChange.batch_id, db.func.min(PriceChange.created_at), db.func.max(PriceChange.percent),
        db.func.max(PriceChange.applies_to), db.func.count(PriceChange.id),
        db.func.count(PriceChange.reverted_at), db.func.max(PriceChange.user_id))
        .filter(PriceChange.tenant_id == tenant_id)
        .group_by(PriceChange.batch_id)
        .order_by(db.func.min(PriceChange.created_at).desc())
        .limit(limit).all())
    from ..models.user import User
    names = {u.id: u.username for u in User.query.filter(User.id.in_([r[6] for r in rows if r[6]])).all()} if rows else {}
    return [{'batch_id': b, 'created_at': at, 'percent': pct, 'applies_to': ap, 'count': n,
             'reverted': rv, 'user': names.get(uid, '—')} for b, at, pct, ap, n, rv, uid in rows]


def revert_batch(tenant_id, user_id, batch_id):
    """
    Devuelve los precios anteriores. Solo toca los productos cuyo precio sigue siendo el que dejó
    esa operación: si alguien lo cambió después, se respeta ese cambio y se informa.
    Devuelve (restaurados, omitidos).
    """
    try:
        changes = (PriceChange.query.filter_by(tenant_id=tenant_id, batch_id=batch_id)
                   .filter(PriceChange.reverted_at.is_(None)).order_by(PriceChange.product_id).all())
        if not changes:
            raise ValidationFailure('Esa operación no existe o ya fue revertida.')
        products = {p.id: p for p in Product.query.filter(
            Product.tenant_id == tenant_id, Product.id.in_([c.product_id for c in changes]))
            .order_by(Product.id).with_for_update().all()}
        restored = skipped = 0
        now = datetime.utcnow()
        for c in changes:
            p = products.get(c.product_id)
            if p is None or p.cost_price != c.new_cost or p.sale_price != c.new_sale:
                skipped += 1
                continue
            p.cost_price, p.sale_price = c.old_cost, c.old_sale
            c.reverted_at = now
            restored += 1
        if not restored:
            raise ValidationFailure('Los precios ya fueron modificados después: no hay nada para revertir.')
        db.session.commit()
        return restored, skipped
    except Exception:
        db.session.rollback()
        raise
