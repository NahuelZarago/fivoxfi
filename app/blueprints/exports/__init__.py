from flask import Blueprint

exports_bp = Blueprint('exports', __name__, template_folder='templates')

from . import routes  # noqa: F401, E402
