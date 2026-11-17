from flask import Blueprint

catalog_bp = Blueprint('catalog', __name__, template_folder='templates')

from . import routes  # noqa: F401, E402
