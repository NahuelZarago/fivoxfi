"""Tema oscuro: toda clase de color que usen las plantillas debe tener su versión oscura (o estar declarada como "igual en ambos")."""
import glob
import re

# Clases que se ven bien en los dos temas tal como están (fondos de color fuerte con texto blanco, menú lateral oscuro,
# avisos, degradados de marca...). Si agregás una acá, es porque revisaste que se lee bien sobre fondo claro y oscuro.
SAME_IN_BOTH = {
    'text-white', 'bg-black', 'bg-black/50',
    'bg-gray-700', 'bg-gray-800', 'bg-gray-950', 'border-gray-800', 'text-gray-300', 'text-gray-800',
    'bg-green-300/10', 'bg-green-400', 'bg-green-400/10', 'bg-green-500', 'bg-green-500/10', 'bg-green-600', 'bg-green-700',
    'border-green-400', 'border-green-500', 'border-green-600',
    'text-green-100', 'text-green-300', 'text-green-400', 'text-green-500',
    'bg-red-500', 'bg-red-600', 'bg-red-700', 'border-red-400', 'bg-amber-500', 'bg-amber-500/20',
    'text-amber-300', 'text-amber-400', 'text-amber-500',
    'bg-white/10', 'bg-white/20', 'border-white/10', 'border-white/20', 'border-white/30',
    'from-gray-50', 'to-green-50',                      # el degradado se redefine en body.bg-gradient-to-br
    'bg-red-100', 'bg-amber-100',                       # (también tienen versión oscura; se listan por si se usan sin ella)
}
# Páginas que NO tienen tema oscuro (landing pública y comprobantes): sus clases no cuentan.
EXCLUDED = ('email/', 'pos/ticket.html', 'cash/print.html')

COLOR = re.compile(r'(?<![\w:/-])((?:hover:)?(?:bg|text|border|divide)-(?:white|black|gray-\d+|green-\d+|red-\d+|amber-\d+)(?:/\d+)?)(?![\w-])')


def _used_classes():
    used = {}
    files = glob.glob('app/**/*.html', recursive=True) + glob.glob('app/static/js/*.js')
    for path in files:
        norm = path.replace('\\', '/')
        if any(x in norm for x in EXCLUDED):
            continue
        for cls in COLOR.findall(open(path, encoding='utf-8').read()):
            used.setdefault(cls, norm)
    return used


def _dark_classes():
    css = open('app/static/css/dark.css', encoding='utf-8').read()
    found = set()
    for m in re.finditer(r'\.((?:hover\\:)?(?:bg|text|border|divide)-[a-z0-9/\\\-]+)', css):
        found.add(m.group(1).replace('\\:', ':').replace('\\/', '/'))
    return found


def test_every_color_class_has_a_dark_version():
    dark = _dark_classes()
    missing = {c: f for c, f in _used_classes().items()
               if c not in dark and c not in SAME_IN_BOTH and c.replace('hover:', '') not in SAME_IN_BOTH
               and not c.startswith('hover:bg-green-') and not c.startswith('hover:bg-red-')
               and c not in ('hover:text-white', 'hover:bg-gray-800', 'hover:bg-white/10', 'hover:bg-green-500')}
    assert not missing, ('Faltan en app/static/css/dark.css (o en SAME_IN_BOTH de este test): '
                         + ', '.join(f'{c} ({f})' for c, f in sorted(missing.items())))


def test_dark_css_has_toggle_and_scoping():
    css = open('app/static/css/dark.css', encoding='utf-8').read()
    assert 'html.dark' in css and '.theme-icon-sun' in css and 'color-scheme: dark' in css
    head = open('app/templates/_head.html', encoding='utf-8').read()
    assert 'js/theme.js' in head and 'css/dark.css' in head and 'themeable' in head


def test_toggle_present_in_every_base_and_public_page():
    for path in ('app/templates/base_app.html', 'app/templates/base_auth.html',
                 'app/blueprints/public/templates/public/index.html',
                 'app/blueprints/public/templates/public/contact.html',
                 'app/blueprints/public/templates/public/product_landing.html'):
        assert 'theme_toggle(' in open(path, encoding='utf-8').read(), path
    # en la app ya no va en el menú lateral sino arriba a la derecha
    assert "theme_toggle('sidebar')" not in open('app/templates/base_app.html', encoding='utf-8').read()


def test_theme_js_persists_choice():
    js = open('app/static/js/theme.js', encoding='utf-8').read()
    assert "fivox-theme" in js and 'prefers-color-scheme' in js and 'data-theme-toggle' in js and "classList.toggle('dark'" in js
