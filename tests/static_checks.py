"""
Verificaciones estáticas que no necesitan base de datos ni extensiones:
 1. Todas las plantillas Jinja compilan.
 2. Todo url_for('x.y') apunta a un endpoint que existe.
 3. Todo `from ...modulo import nombre` de blueprints/servicios existe de verdad.
 4. Todo <form method=POST> incluye csrf_input().
Uso: python tests/static_checks.py
"""
import ast, glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
errors = []

# 1. plantillas
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError
dirs = ['app/templates'] + glob.glob('app/blueprints/*/templates')
env = Environment(loader=FileSystemLoader(dirs), extensions=[])
for f in glob.glob('app/**/*.html', recursive=True):
    src = open(f, encoding='utf-8').read()
    try:
        env.parse(src)
    except TemplateSyntaxError as e:
        errors.append(f'Jinja {f}:{e.lineno} {e.message}')
    for m in re.finditer(r'<form\b[^>]*method=["\']?POST[^>]*>(.*?)</form>', src, re.S | re.I):
        if 'csrf_input()' not in m.group(1):
            errors.append(f'CSRF faltante en un <form POST> de {f}')

# 2. endpoints
endpoints = {'static'}
for rf in glob.glob('app/blueprints/*/routes.py'):
    bp = rf.split(os.sep)[2]
    for n in ast.walk(ast.parse(open(rf).read())):
        if isinstance(n, ast.FunctionDef) and any(
                isinstance(d, ast.Call) and getattr(d.func, 'attr', '') == 'route' for d in n.decorator_list):
            endpoints.add(f'{bp}.{n.name}')
for f in glob.glob('app/**/*.html', recursive=True) + glob.glob('app/**/*.py', recursive=True):
    for m in re.finditer(r"url_for\(\s*'([\w.]+)'", open(f, encoding='utf-8').read()):
        if m.group(1) not in endpoints:
            errors.append(f'Endpoint inexistente {m.group(1)!r} en {f}')

# 3. imports relativos
def module_names(path):
    t = ast.parse(open(path).read())
    names = set()
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)): names.add(n.name)
        elif isinstance(n, ast.Assign):
            for tg in n.targets:
                if isinstance(tg, ast.Name): names.add(tg.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names: names.add((a.asname or a.name).split('.')[0])
    return names

for f in glob.glob('app/**/*.py', recursive=True):
    tree = ast.parse(open(f).read())
    pkg = os.path.dirname(f).split(os.sep)
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level > 0:
            base = pkg[: len(pkg) - (n.level - 1)]
            target = os.path.join(*base, *(n.module.split('.') if n.module else []))
            cand = target + '.py' if os.path.isfile(target + '.py') else os.path.join(target, '__init__.py')
            if not os.path.isfile(cand):
                if n.module is None and all(os.path.isfile(os.path.join(target, a.name + '.py')) for a in n.names):
                    continue
                errors.append(f'Import relativo roto en {f}: {"." * n.level}{n.module}'); continue
            have = module_names(cand)
            for a in n.names:
                if a.name != '*' and a.name not in have and not os.path.isfile(os.path.join(os.path.dirname(cand), a.name + '.py')) and not os.path.isfile(os.path.join(os.path.dirname(cand), a.name, '__init__.py')):
                    errors.append(f'{f}: "{a.name}" no existe en {cand}')

print('\n'.join(errors) if errors else 'static checks OK')
sys.exit(1 if errors else 0)
