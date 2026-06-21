from flask import render_template
from . import public_bp


@public_bp.route('/')
def index():
    return render_template('public/index.html')


@public_bp.route('/producto/<string:slug>')
def product_landing(slug):
    return render_template('public/product_landing.html', slug=slug)


@public_bp.route('/contacto')
def contact():
    return render_template('public/contact.html')
