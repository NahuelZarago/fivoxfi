"""Categorías y proveedores de un negocio."""
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.catalog import Category, Supplier
from ..models.product import Product
from ..utils.validation import ValidationFailure

MAX_CATEGORIES = 200
MAX_SUPPLIERS = 500


def resolve_ref(model, tenant_id, raw, label):
    """'' o None -> None. Un id -> el id, solo si pertenece a este negocio (nunca se confía en el formulario)."""
    if raw is None or str(raw).strip() == '':
        return None
    try:
        ref_id = int(str(raw).strip())
    except ValueError:
        raise ValidationFailure(f'{label} inválida.')
    if db.session.query(model.id).filter_by(id=ref_id, tenant_id=tenant_id).first() is None:
        raise ValidationFailure(f'{label} inválida.')
    return ref_id


def _name_taken(model, tenant_id, name, exclude_id=None):
    q = model.query.filter(model.tenant_id == tenant_id, db.func.lower(model.name) == name.lower())
    if exclude_id:
        q = q.filter(model.id != exclude_id)
    return q.first() is not None


def _own(model, tenant_id, ref_id):
    obj = model.query.filter_by(id=ref_id, tenant_id=tenant_id).first()
    if obj is None:
        raise ValidationFailure('No se encontró el elemento.')
    return obj


# ── categorías ─────────────────────────────────────────────
def create_category(tenant_id, name):
    if Category.query.filter_by(tenant_id=tenant_id).count() >= MAX_CATEGORIES:
        raise ValidationFailure(f'Máximo {MAX_CATEGORIES} categorías.')
    if _name_taken(Category, tenant_id, name):
        raise ValidationFailure('Ya existe una categoría con ese nombre.')
    try:
        cat = Category(tenant_id=tenant_id, name=name)
        db.session.add(cat)
        db.session.commit()
        return cat
    except IntegrityError:
        db.session.rollback()
        raise ValidationFailure('Ya existe una categoría con ese nombre.')


def rename_category(tenant_id, category_id, name):
    cat = _own(Category, tenant_id, category_id)
    if _name_taken(Category, tenant_id, name, exclude_id=cat.id):
        raise ValidationFailure('Ya existe una categoría con ese nombre.')
    try:
        cat.name = name
        db.session.commit()
        return cat
    except IntegrityError:
        db.session.rollback()
        raise ValidationFailure('Ya existe una categoría con ese nombre.')


def delete_category(tenant_id, category_id):
    """Borra la categoría; sus productos quedan "sin categoría". Devuelve cuántos productos tenía."""
    cat = _own(Category, tenant_id, category_id)
    try:
        n = Product.query.filter_by(tenant_id=tenant_id, category_id=cat.id).update(
            {Product.category_id: None}, synchronize_session=False)
        Category.query.filter_by(id=cat.id, tenant_id=tenant_id).delete(synchronize_session=False)
        db.session.commit()
        return n
    except Exception:
        db.session.rollback()
        raise


def category_rows(tenant_id):
    counts = dict(db.session.query(Product.category_id, db.func.count(Product.id))
                  .filter(Product.tenant_id == tenant_id, Product.category_id.isnot(None))
                  .group_by(Product.category_id).all())
    cats = Category.query.filter_by(tenant_id=tenant_id).order_by(db.func.lower(Category.name)).all()
    return [(c, int(counts.get(c.id, 0))) for c in cats]


# ── proveedores ────────────────────────────────────────────
def save_supplier(tenant_id, data, supplier_id=None):
    if supplier_id is None and Supplier.query.filter_by(tenant_id=tenant_id).count() >= MAX_SUPPLIERS:
        raise ValidationFailure(f'Máximo {MAX_SUPPLIERS} proveedores.')
    if _name_taken(Supplier, tenant_id, data['name'], exclude_id=supplier_id):
        raise ValidationFailure('Ya existe un proveedor con ese nombre.')
    try:
        if supplier_id is None:
            sup = Supplier(tenant_id=tenant_id, **data)
            db.session.add(sup)
        else:
            sup = _own(Supplier, tenant_id, supplier_id)
            for k, v in data.items():
                setattr(sup, k, v)
        db.session.commit()
        return sup
    except IntegrityError:
        db.session.rollback()
        raise ValidationFailure('Ya existe un proveedor con ese nombre.')


def delete_supplier(tenant_id, supplier_id):
    sup = _own(Supplier, tenant_id, supplier_id)
    try:
        n = Product.query.filter_by(tenant_id=tenant_id, supplier_id=sup.id).update(
            {Product.supplier_id: None}, synchronize_session=False)
        Supplier.query.filter_by(id=sup.id, tenant_id=tenant_id).delete(synchronize_session=False)
        db.session.commit()
        return n
    except Exception:
        db.session.rollback()
        raise


def get_supplier(tenant_id, supplier_id):
    return _own(Supplier, tenant_id, supplier_id)


def supplier_rows(tenant_id):
    counts = dict(db.session.query(Product.supplier_id, db.func.count(Product.id))
                  .filter(Product.tenant_id == tenant_id, Product.supplier_id.isnot(None))
                  .group_by(Product.supplier_id).all())
    sups = Supplier.query.filter_by(tenant_id=tenant_id).order_by(db.func.lower(Supplier.name)).all()
    return [(s, int(counts.get(s.id, 0))) for s in sups]
