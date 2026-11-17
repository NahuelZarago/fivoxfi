from flask import Blueprint

cash_bp = Blueprint('cash', __name__, template_folder='templates')

from . import routes  # noqa: F401, E402
