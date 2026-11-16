import pytest

# Fixtures de los tests con base de datos. Todo se importa dentro de cada fixture
# para que los tests de módulos puros corran aun sin las dependencias instaladas.


@pytest.fixture()
def app():
    pytest.importorskip('flask_sqlalchemy')
    from app import create_app
    from app.extensions import db
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def shop(app):
    """Un negocio con dueño, empleado, cliente y un producto."""
    from .helpers import make_product, make_tenant, make_user
    t = make_tenant()
    return {
        'tenant': t,
        'owner': make_user(t, 'owner'),
        'employee': make_user(t, 'employee'),
        'client': make_user(t, 'client'),
        'product': make_product(t),
    }
