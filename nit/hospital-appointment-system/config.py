# ============================================================
# AI-Based Hospital Appointment Scheduling System
# Configuration Module
# ============================================================

import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()


class Config:
    """Base configuration class."""
    
    # Flask Core
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    
    # Database
    # Default: SQLite (works out of the box, no server required)
    # For MySQL: set DATABASE_URL=mysql+pymysql://user:pass@host/dbname in .env
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(BASE_DIR, 'hospital_scheduler.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT Settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-dev-secret')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    )
    
    # Mail Settings (for notification simulation)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')

    # Doctor onboarding verification
    DOCTOR_ALLOWED_EMAIL_DOMAINS = [
        domain.strip().lower()
        for domain in os.environ.get('DOCTOR_ALLOWED_EMAIL_DOMAINS', 'hospital.com').split(',')
        if domain.strip()
    ]
    
    # Scheduling Parameters
    SLOT_DURATION_MINUTES = int(os.environ.get('SLOT_DURATION_MINUTES', 30))
    WORKING_HOURS_START = os.environ.get('WORKING_HOURS_START', '09:00')
    WORKING_HOURS_END = os.environ.get('WORKING_HOURS_END', '17:00')
    MAX_PATIENTS_PER_SLOT = int(os.environ.get('APPOINTMENTS_PER_SLOT', 1))
    
    # Priority Weights for AI Scheduler
    PRIORITY_WEIGHTS = {
        'emergency': 100,
        'senior_citizen': 50,
        'follow_up': 30,
        'normal': 10
    }


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Configuration dictionary
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
