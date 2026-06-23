from flask import Flask
from .extensions import db, login_manager, migrate, mail
from config import config


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)

    from .models import user, tenant, product, sale  # noqa: F401

    from .blueprints.public import public_bp
    from .blueprints.auth import auth_bp
    from .blueprints.dashboard import dashboard_bp
    from .blueprints.inventory import inventory_bp
    from .blueprints.pos import pos_bp
    from .blueprints.reports import reports_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/app/dashboard')
    app.register_blueprint(inventory_bp, url_prefix='/app/inventory')
    app.register_blueprint(pos_bp, url_prefix='/app/pos')
    app.register_blueprint(reports_bp, url_prefix='/app/reports')

    return app
