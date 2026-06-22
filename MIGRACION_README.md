# Instrucciones para migrar la base de datos

## Si es una base de datos NUEVA (primera vez):
```bash
flask db init
flask db migrate -m "Initial schema v2"
flask db upgrade
```

## Si ya tenías datos anteriores (base de datos existente):
```bash
flask db migrate -m "Add employee_code and refactor user roles"
flask db upgrade
```

El sistema detectará automáticamente:
- Nueva columna `employee_code` en la tabla `tenants`
- Cambio de `is_confirmed` → `is_email_confirmed` en `users`
- `role` ahora puede ser 'owner' | 'seller' | NULL
- `tenant_id` en `users` ahora es nullable
