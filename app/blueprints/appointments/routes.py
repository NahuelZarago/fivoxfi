from flask import render_template

from . import appointments_bp
from ...utils.decorators import login_required_with_tenant, require
from ...utils.permissions import APPOINTMENTS_VIEW


@appointments_bp.route('/')
@login_required_with_tenant
@require(APPOINTMENTS_VIEW)
def index():
    # Módulo 2: todavía en construcción. Cuando exista, esta ruta mostrará la agenda.
    return render_template('appointments/maintenance.html')
