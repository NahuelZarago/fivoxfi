from flask import flash, jsonify, redirect, render_template, request
from flask_login import current_user


def _json_wanted():
    return request.path.startswith('/app/pos/api') or request.is_json


def register_error_handlers(app):
    def make(code, title, message):
        def handler(error):
            if code == 400 and getattr(error, 'description', '') == 'csrf':
                if _json_wanted():
                    return jsonify({'error': 'Sesión de seguridad vencida. Recargá la página.'}), 400
                flash('La página estuvo abierta demasiado tiempo. Probá de nuevo.', 'warning')
                return redirect(request.referrer or '/')
            if _json_wanted():
                return jsonify({'error': message}), code
            return render_template('errors/error.html', code=code, title=title, message=message,
                                   authenticated=current_user.is_authenticated), code
        return handler

    for code, title, msg in [
        (400, 'Solicitud inválida', 'No pudimos procesar lo que enviaste.'),
        (403, 'Sin permiso', 'No tenés permiso para ver esta página.'),
        (404, 'Página no encontrada', 'La página que buscás no existe o fue movida.'),
        (405, 'Método no permitido', 'Esa acción no está permitida.'),
        (413, 'Archivo demasiado grande', 'Lo que enviaste supera el tamaño permitido.'),
        (429, 'Demasiados intentos', 'Hiciste muchas solicitudes seguidas. Esperá un momento e intentá de nuevo.'),
    ]:
        app.register_error_handler(code, make(code, title, msg))

    def server_error(error):
        from .extensions import db
        db.session.rollback()
        app.logger.exception('Error 500')
        if _json_wanted():
            return jsonify({'error': 'Error interno. Intentá de nuevo.'}), 500
        return render_template('errors/error.html', code=500, title='Algo salió mal',
                               message='Tuvimos un problema de nuestro lado. Ya quedó registrado.',
                               authenticated=current_user.is_authenticated), 500

    app.register_error_handler(500, server_error)
