# Fivox

SaaS multi-negocio de **Stock y Finanzas** (activo) y **Turnos y Recordatorios** (en construcción).
Flask · PostgreSQL · Jinja · Tailwind.

## Roles
| Rol | Cómo entra | Qué puede |
|---|---|---|
| Dueño | "Registrar mi empresa" | Todo: stock, ventas, reportes, anular ventas, equipo, códigos |
| Empleado | Código `FX-XXXXXX` | Vender, ver inventario (sin costos), reponer stock |
| Cliente | Código `FC-XXXXXX` | Módulo Turnos (hoy: pantalla "en mantenimiento") |

Los permisos viven en un único lugar: `app/utils/permissions.py`.

## Puesta en marcha (local)
```bash
cp .env.example .env              # completá SECRET_KEY y DATABASE_URL
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
flask --app run db upgrade
flask --app run run --debug       # http://127.0.0.1:5000
```
Con Docker: `docker compose up --build` (levanta Postgres, Redis y la app en :8000, y aplica migraciones).

> **Base existente (v2):** `flask --app run db upgrade` aplica la migración `004` sin perder datos:
> renombra el rol `seller→employee`, crea códigos de cliente, corrige negativos, y registra el stock actual como "stock inicial".

## Novedades v4
- **Actualizar precios por %** (Inventario → *Actualizar precios*): subir o bajar costo, venta o ambos; redondeo; a todos o por búsqueda; vista previa, historial y **revertir**.
- **Exportar datos** (*Exportar datos*): productos, ventas y movimientos en Excel (.xlsx) o CSV. Sin librerías extra.
- **Panel de administrador** (`/admin`): estadísticas, negocios (suspender, plan, eliminar) y usuarios (activar, verificar email, eliminar). Para los demás usuarios la ruta responde 404.
- **Eliminar mi cuenta** (Configuración) para empleados y clientes.

Para ser administrador (una sola vez, con la cuenta ya registrada):
```bash
docker compose exec web flask --app run make-admin tu@email.com   # sin Docker: flask --app run make-admin tu@email.com
# para quitarlo: flask --app run remove-admin tu@email.com
```
La migración `005` (columna `is_superadmin` y tabla `price_changes`) se aplica sola con `db upgrade`.

## Novedades v5
- **Caja** (menú *Caja*, dueño y empleados): se abre con el efectivo inicial y se cierra contando el efectivo. Calcula lo esperado (inicial + ventas en efectivo del turno, sin anuladas) y muestra si sobra o falta. Una sola caja abierta por negocio; el dueño ve el historial de cierres.
- **Tickets**: tras cada venta, "Ver / imprimir ticket" (formato 80 mm, comprobante no fiscal). También desde el historial de ventas. Cada empleado ve solo sus tickets.
- Migración `006` (tabla `cash_sessions`), se aplica sola con `db upgrade`.

## Novedades v6
- **Categorías** y **proveedores** (menú *Categorías* / *Proveedores*, solo dueño): se asignan al crear o editar un producto.
- El inventario se filtra por categoría (incluye "Sin categoría") y por proveedor; los empleados no ven proveedores (es información de compras).
- *Actualizar precios* puede aplicarse a una categoría completa.
- La exportación de productos incluye categoría y proveedor.
- Migración `007` (tablas `categories` y `suppliers`, columnas en `products`). Borrar una categoría o proveedor no borra productos.

## Tests
```bash
python tests/static_checks.py   # plantillas, endpoints, imports, CSRF en formularios
python tests/render_check.py    # renderiza todas las plantillas con datos de prueba
pytest                          # unitarios + integración (usa SQLite o TEST_DATABASE_URL de Postgres)
```
Sugerido: correr `pytest` con `TEST_DATABASE_URL` apuntando a un Postgres para validar los `CHECK`/FK reales.

## Producción — checklist
- `APP_ENV=production`, `SECRET_KEY` de 32+ caracteres (la app **no arranca** si no).
- HTTPS + `TRUST_PROXY=true` detrás de Nginx/Render.
- `RATELIMIT_STORAGE_URI=redis://...` (con memoria, cada worker cuenta aparte).
- **Compilar Tailwind** (el CDN es solo para desarrollo):
  ```bash
  npx tailwindcss@3 -c tailwind.config.js -i app/static/css/input.css -o app/static/css/app.css --minify
  # y poner USE_COMPILED_CSS=true
  ```
- Configurar `SUPPORT_WHATSAPP` y el email SMTP.
- Si el repo tiene `__pycache__` versionado: `git rm -r --cached $(git ls-files | grep __pycache__)`.

## Pendiente (a propósito, para el final)
- **Mercado Pago / tarjeta**: cobro de suscripción y/o ventas. Ya está preparado el terreno: `@csrf_exempt` para webhooks firmados y el medio de pago `mercadopago` en `services/sales.py`.
- **Inicio de sesión con Google** (OAuth): hay un comentario en `auth/login.html` donde va el botón.
- Módulo **Turnos y Recordatorios** (hoy en mantenimiento, `app/blueprints/appointments`).
- Ideas: numeración de ventas por negocio, CSP estricta, 2FA para dueños.
