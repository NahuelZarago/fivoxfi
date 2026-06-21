# SaasHub — Sistema de Gestión para Negocios Locales

## Requisitos previos
- Python 3.10 o superior
- PostgreSQL instalado y corriendo

## Instalación paso a paso

### 1. Crear entorno virtual e instalar dependencias
```bash
python -m venv venv

# En Windows:
venv\Scripts\activate

# En Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar variables de entorno
```bash
# Copiar el archivo de ejemplo
copy .env.example .env   # Windows
cp .env.example .env     # Mac/Linux

# Editar .env con tus datos de PostgreSQL
```

### 3. Crear la base de datos en PostgreSQL
Abrí pgAdmin o psql y ejecutá:
```sql
CREATE DATABASE saas_hub_dev;
```

### 4. Inicializar y migrar la base de datos
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 5. Ejecutar el servidor
```bash
python run.py
```

Abrí tu navegador en: http://localhost:5000

## Estructura de URLs

| Ruta | Descripción | Acceso |
|------|-------------|--------|
| `/` | Landing page / Catálogo | Público |
| `/auth/registro` | Crear nueva cuenta | Público |
| `/auth/login` | Iniciar sesión | Público |
| `/app/dashboard/` | Panel principal | Admin + Vendedor |
| `/app/pos/terminal` | Punto de Venta | Admin + Vendedor |
| `/app/inventory/productos` | Inventario | Solo Admin |
| `/app/reports/cierre-diario` | Cierre de caja | Solo Admin |
| `/app/reports/historial-ventas` | Historial | Solo Admin |

## Variables de entorno (.env)

```
FLASK_ENV=development
SECRET_KEY=tu-clave-secreta-larga-y-aleatoria
DEV_DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/saas_hub_dev
```
