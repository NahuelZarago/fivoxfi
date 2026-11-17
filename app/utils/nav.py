"""
Menú lateral. Se arma según el rol: cada persona ve solo lo que puede usar.

Turnos aparece en el menú con su estado ("maintenance") y lleva a la pantalla
de "Módulo en mantenimiento".
"""
from .permissions import (
    APPOINTMENTS_VIEW, CASH_MANAGE, INVENTORY_MANAGE, INVENTORY_VIEW, MODULE_STATUS, POS_SELL, REPORTS_VIEW,
    TEAM_MANAGE, can,
)

GROUP_STOCK = 'Stock y finanzas'
GROUP_APPOINTMENTS = 'Turnos'
GROUP_ACCOUNT = 'Cuenta'

# Íconos (trazos de 24x24, estilo outline). Cada ícono es una lista de paths.
ICONS = {
    'grid': ['M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z'],
    'chart': ['M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z'],
    'cash': ['M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 11h.01M12 11h.01M15 11h.01M4 19h16a2 2 0 002-2V7a2 2 0 00-2-2H4a2 2 0 00-2 2v10a2 2 0 002 2z'],
    'box': ['M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4'],
    'swap': ['M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4'],
    'drawer': ['M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.6a2 2 0 00-1.8 1.1l-.6 1.2a2 2 0 01-1.8 1.1h-2.4a2 2 0 01-1.8-1.1l-.6-1.2A2 2 0 007.6 13H4'],
    'folder': ['M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z'],
    'truck': ['M3 7h11v9H3zM14 10h4l3 3v3h-7zM7 19a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM17 19a1.5 1.5 0 100-3 1.5 1.5 0 000 3z'],
    'tag': ['M7 7h.01M7 3h5c.5 0 1 .2 1.4.6l7 7a2 2 0 010 2.8l-5 5a2 2 0 01-2.8 0l-7-7A2 2 0 013 10V5a2 2 0 012-2z'],
    'download': ['M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5m0 0l5-5m-5 5V4'],
    'report': ['M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z'],
    'calendar': ['M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z'],
    'cog': ['M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z',
            'M15 12a3 3 0 11-6 0 3 3 0 016 0z'],
    'users': ['M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z'],
    'logout': ['M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1'],
}

# match: prefijos de endpoint que dejan el ítem "activo".
# module: clave en MODULE_STATUS (si no está, el ítem se considera activo).
NAV_ITEMS = (
    dict(key='home', label='Mis aplicaciones', endpoint='dashboard.index', icon='grid',
         capability=None, group=None, match=('dashboard.index',)),
    dict(key='panel', label='Panel de control', endpoint='dashboard.gestion', icon='chart',
         capability=REPORTS_VIEW, group=GROUP_STOCK, match=('dashboard.gestion',)),
    dict(key='pos', label='Punto de venta', endpoint='pos.terminal', icon='cash',
         capability=POS_SELL, group=GROUP_STOCK, match=('pos.',)),
    dict(key='cash', label='Caja', endpoint='cash.index', icon='drawer',
         capability=CASH_MANAGE, group=GROUP_STOCK, match=('cash.',)),
    dict(key='inventory', label='Inventario', endpoint='inventory.product_list', icon='box',
         capability=INVENTORY_VIEW, group=GROUP_STOCK, module='inventory',
         match=('inventory.product', 'inventory.stock')),
    dict(key='movements', label='Movimientos', endpoint='inventory.movement_list', icon='swap',
         capability=REPORTS_VIEW, group=GROUP_STOCK, match=('inventory.movement',)),
    dict(key='categories', label='Categorías', endpoint='catalog.categories', icon='folder',
         capability=INVENTORY_MANAGE, group=GROUP_STOCK, match=('catalog.categor',)),
    dict(key='suppliers', label='Proveedores', endpoint='catalog.suppliers', icon='truck',
         capability=INVENTORY_MANAGE, group=GROUP_STOCK, match=('catalog.supplier',)),
    dict(key='prices', label='Actualizar precios', endpoint='inventory.price_update', icon='tag',
         capability=INVENTORY_MANAGE, group=GROUP_STOCK, match=('inventory.price',)),
    dict(key='reports', label='Reportes', endpoint='reports.daily_close', icon='report',
         capability=REPORTS_VIEW, group=GROUP_STOCK, match=('reports.',)),
    dict(key='exports', label='Exportar datos', endpoint='exports.index', icon='download',
         capability=REPORTS_VIEW, group=GROUP_STOCK, match=('exports.',)),
    dict(key='appointments', label='Turnos y recordatorios', endpoint='appointments.index', icon='calendar',
         capability=APPOINTMENTS_VIEW, group=GROUP_APPOINTMENTS, module='appointments',
         match=('appointments.',)),
    dict(key='settings', label='Configuración', endpoint='dashboard.settings', icon='cog',
         capability=None, group=GROUP_ACCOUNT, match=('dashboard.settings',)),
    dict(key='team', label='Equipo', endpoint='dashboard.employees', icon='users',
         capability=TEAM_MANAGE, group=GROUP_ACCOUNT, match=('dashboard.employee',)),
)


def build_nav(role, endpoint, badges=None):
    """
    Devuelve los grupos del menú para este rol:
        [{'title': 'Stock y finanzas'|None, 'items': [{label, endpoint, icon, active, status, badge}]}]
    `badges` = {'inventory': 3} muestra un contador (ej. productos con stock bajo).
    """
    badges = badges or {}
    groups = []
    for spec in NAV_ITEMS:
        capability = spec['capability']
        if capability is not None and not can(role, capability):
            continue
        item = {
            'key': spec['key'],
            'label': spec['label'],
            'endpoint': spec['endpoint'],
            'icon': ICONS[spec['icon']],
            'active': bool(endpoint) and any(endpoint.startswith(p) for p in spec['match']),
            'status': MODULE_STATUS.get(spec.get('module'), 'active'),
            'badge': badges.get(spec['key']) or 0,
        }
        if not groups or groups[-1]['title'] != spec['group']:
            groups.append({'title': spec['group'], 'items': []})
        groups[-1]['items'].append(item)
    return groups
