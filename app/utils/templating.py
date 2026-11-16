from datetime import datetime

from flask import request
from flask_login import current_user

from .formatting import format_local_dt, format_money, format_money0
from .nav import build_nav


def register_filters(app):
    from ..models.stock_movement import REASON_LABELS
    from ..services.sales import PAYMENT_METHODS

    app.jinja_env.filters['money'] = format_money
    app.jinja_env.filters['money0'] = format_money0
    app.jinja_env.filters['local_dt'] = format_local_dt
    app.jinja_env.filters['reason_label'] = lambda r: REASON_LABELS.get(r, r)
    app.jinja_env.filters['payment_label'] = lambda m: PAYMENT_METHODS.get(m, m)


def register_context(app):
    @app.context_processor
    def inject_globals():
        ctx = {
            'current_year': datetime.utcnow().year,
            'support_whatsapp': app.config.get('SUPPORT_WHATSAPP'),
            'use_compiled_css': app.config.get('USE_COMPILED_CSS'),
            'can': lambda cap: current_user.is_authenticated and current_user.can(cap),
            'nav_groups': [],
        }
        if current_user.is_authenticated and getattr(current_user, 'has_role', False):
            badges = {}
            try:
                if current_user.tenant_id and current_user.can('inventory.view'):
                    from ..services.metrics import low_stock_count
                    n = low_stock_count(current_user.tenant_id)
                    if n:
                        badges['inventory'] = n
            except Exception:  # noqa: BLE001 - una falla del badge no debe romper la página
                app.logger.exception('No se pudo calcular el badge de stock bajo')
            ctx['nav_groups'] = build_nav(current_user.role, request.endpoint, badges)
        return ctx
