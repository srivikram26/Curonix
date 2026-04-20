# ============================================================
# Flask Application Factory
# Creates and configures the Flask application instance
# ============================================================

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from config import config_map

# Initialize extensions (will be bound to app in create_app)
db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_name='default'):
    """
    Application factory pattern.
    Creates and configures the Flask application.
    
    Args:
        config_name (str): Configuration to use ('development', 'production', 'testing')
    
    Returns:
        Flask: Configured Flask application instance
    """
    app = Flask(
        __name__,
        static_folder='../static',
        template_folder='../templates'
    )
    
    # Load configuration
    app.config.from_object(config_map.get(config_name, config_map['default']))
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    CORS(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login_page'
    login_manager.login_message_category = 'info'
    
    # Register blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.patient_routes import patient_bp
    from app.routes.doctor_routes import doctor_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.api_routes import api_bp
    from app.routes.main_routes import main_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(patient_bp, url_prefix='/patient')
    app.register_blueprint(doctor_bp, url_prefix='/doctor')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Create database tables
    with app.app_context():
        from app import models
        db.create_all()
    
    return app
