from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from . import cash_bp
from ...extensions import db
from ...models.cash_session import CashSession
from ...services import cash
from ...utils.decorators import login_required_with_tenant, require
from ...utils.formatting import format_money
from ...utils.permissions import CASH_MANAGE, REPORTS_VIEW
from ...utils.validation import ValidationFailure, clean_text, parse_money


@cash_bp.route('/')
@login_required_with_tenant
@require(CASH_MANAGE)
def index():
    session = cash.current_session(current_user.tenant_id)
    page = request.args.get('page', 1, type=int)
    history = None
    if current_user.can(REPORTS_VIEW):
        history = (CashSession.query.filter(CashSession.tenant_id == current_user.tenant_id,
                                            CashSession.closed_at.isnot(None))
                   .order_by(CashSession.closed_at.desc()).paginate(page=page, per_page=15, error_out=False))
    return render_template('cash/index.html', session=session,
                           s=cash.summary(session) if session else None, history=history)


@cash_bp.route('/abrir', methods=['POST'])
@login_required_with_tenant
@require(CASH_MANAGE)
def open_cash():
    try:
        amount = parse_money(request.form.get('opening_amount', ''), 'El monto inicial')
        cash.open_session(current_user.tenant_id, current_user.id, amount)
        flash(f'Caja abierta con {format_money(amount)}.', 'success')
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('cash.index'))


@cash_bp.route('/cerrar', methods=['POST'])
@login_required_with_tenant
@require(CASH_MANAGE)
def close_cash():
    try:
        counted = parse_money(request.form.get('counted_cash', ''), 'El efectivo contado')
        note = clean_text(request.form.get('note', ''), 'La nota', max_len=200, required=False)
        session = cash.close_session(current_user.tenant_id, current_user.id, counted, note)
    except ValidationFailure as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('cash.index'))
    diff = session.difference
    if diff == 0:
        flash('Caja cerrada. El efectivo coincide exacto. ✔', 'success')
    else:
        word = 'sobran' if diff > 0 else 'faltan'
        flash(f'Caja cerrada. Esperábamos {format_money(session.expected_cash)}, contaste '
              f'{format_money(session.counted_cash)}: {word} {format_money(abs(diff))}.', 'warning')
    if current_user.can(REPORTS_VIEW):
        return redirect(url_for('cash.detail', session_id=session.id))
    return redirect(url_for('cash.print_view', session_id=session.id))      # el empleado ve su comprobante


@cash_bp.route('/<int:session_id>')
@login_required_with_tenant
@require(REPORTS_VIEW)
def detail(session_id):
    session = CashSession.query.filter_by(id=session_id, tenant_id=current_user.tenant_id).first_or_404()
    return render_template('cash/detail.html', session=session, s=cash.summary(session))


@cash_bp.route('/<int:session_id>/imprimir')
@login_required_with_tenant
@require(CASH_MANAGE)
def print_view(session_id):
    """Comprobante imprimible del cierre. El dueño ve todos; un empleado, solo los que cerró él."""
    session = CashSession.query.filter_by(id=session_id, tenant_id=current_user.tenant_id).first_or_404()
    if session.closed_at is None or (session.closed_by_id != current_user.id and not current_user.can(REPORTS_VIEW)):
        abort(404)
    return render_template('cash/print.html', session=session, s=cash.summary(session),
                           tenant=current_user.tenant, auto_print=request.args.get('print') == '1')
