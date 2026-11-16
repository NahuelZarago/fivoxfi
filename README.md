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
- Ideas: numeración de ventas por negocio, CSP estricta, exportar a Excel/CSV, 2FA para dueños.
