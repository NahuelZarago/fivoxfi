from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail

db = SQLAlchemy()
mail = Mail()
migrate = Migrate()
login_manager = LoginManager()


login_manager.login_view = 'auth.login'
login_manager.login_message = 'Iniciá sesión para acceder a esta sección.'
login_manager.login_message_category = 'warning'
