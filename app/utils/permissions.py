"""
Roles y permisos de Fivox. ÚNICA fuente de verdad.

Las rutas no preguntan "¿es dueño?" sino "¿puede hacer X?" (ver
`decorators.require`). Para cambiar qué puede hacer un rol se edita
ROLE_CAPABILITIES y nada más.

Este módulo no depende de Flask ni de la base de datos.
"""

ROLE_OWNER = 'owner'        # Dueño: control total del negocio
ROLE_EMPLOYEE = 'employee'  # Empleado: vende y repone stock, sin ver costos ni ganancias
ROLE_CLIENT = 'client'      # Cliente: usa el módulo de Turnos

ALL_ROLES = (ROLE_OWNER, ROLE_EMPLOYEE, ROLE_CLIENT)

ROLE_LABELS = {
    ROLE_OWNER: 'Dueño',
    ROLE_EMPLOYEE: 'Empleado',
    ROLE_CLIENT: 'Cliente',
}

# ── Capacidades ────────────────────────────────────────────────────────
INVENTORY_VIEW = 'inventory.view'            # Ver productos y stock (sin costos)
INVENTORY_MANAGE = 'inventory.manage'        # Crear, editar y desactivar productos, ver costos
STOCK_ENTRY = 'stock.entry'                  # Registrar entradas de mercadería
STOCK_ADJUST = 'stock.adjust'                # Registrar mermas y ajustes por conteo
POS_SELL = 'pos.sell'                        # Vender en el punto de venta
SALES_VOID = 'sales.void'                    # Anular ventas
REPORTS_VIEW = 'reports.view'                # Panel de métricas, reportes, historial y movimientos
TEAM_MANAGE = 'team.manage'                  # Equipo y códigos de invitación
BUSINESS_SETTINGS = 'business.settings'      # Datos del negocio
APPOINTMENTS_VIEW = 'appointments.view'      # Módulo de Turnos

ALL_CAPABILITIES = frozenset({
    INVENTORY_VIEW, INVENTORY_MANAGE, STOCK_ENTRY, STOCK_ADJUST, POS_SELL,
    SALES_VOID, REPORTS_VIEW, TEAM_MANAGE, BUSINESS_SETTINGS, APPOINTMENTS_VIEW,
})

ROLE_CAPABILITIES = {
    ROLE_OWNER: ALL_CAPABILITIES,
    ROLE_EMPLOYEE: frozenset({INVENTORY_VIEW, STOCK_ENTRY, POS_SELL}),
    ROLE_CLIENT: frozenset({APPOINTMENTS_VIEW}),
}

# ── Estado de los módulos ──────────────────────────────────────────────
# Reactivar Turnos cuando esté listo = cambiar 'maintenance' por 'active'.
MODULE_STATUS = {
    'inventory': 'active',
    'appointments': 'maintenance',
}

# Pantalla a la que cada rol llega después de iniciar sesión.
HOME_ENDPOINTS = {
    ROLE_OWNER: 'dashboard.index',
    ROLE_EMPLOYEE: 'pos.terminal',
    ROLE_CLIENT: 'appointments.index',
}


def can(role, capability):
    """True si el rol tiene la capacidad. Falla con un nombre inexistente (typo)."""
    if capability not in ALL_CAPABILITIES:
        raise ValueError(f'Capacidad desconocida: {capability!r}')
    return capability in ROLE_CAPABILITIES.get(role, frozenset())


def home_endpoint(role):
    return HOME_ENDPOINTS.get(role, 'auth.choose_role')
