import os

from app import create_app

# APP_ENV: development | production | testing. (FLASK_ENV ya no lo lee Flask 3,
# pero se respeta como alternativa para no romper configuraciones viejas.)
app = create_app(os.environ.get('APP_ENV') or os.environ.get('FLASK_ENV') or 'default')

if __name__ == '__main__':
    # Solo para desarrollo local. En producción: gunicorn run:app
    app.run(debug=app.config['DEBUG'])
