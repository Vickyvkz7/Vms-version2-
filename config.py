"""
Configuration file for KPR College Visitor Management System
Handles different environments: development, testing, and production
"""

import os
from datetime import timedelta

# Base Configuration
class Config:
    """Base configuration with common settings"""
    
    # Application Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kpr-college-secret-key-2024-dev'
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///kpr_visitor.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Login Manager Configuration
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # File Upload Configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Logging Configuration
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'logs/app.log'
    
    # Pagination
    ITEMS_PER_PAGE = 20
    
    # College Departments
    DEPARTMENTS = [
        'Administration',
        'Computer Science',
        'Mathematics',
        'Physics',
        'Chemistry',
        'Biology',
        'Commerce',
        'Business Administration',
        'English',
        'Tamil',
        'Library',
        'Sports',
        'Examination Cell',
        'Placement Cell',
        'Hostel',
        'Accounts',
        'Transport',
        'Security',
        'Cafeteria',
        'Maintenance'
    ]
    
    # Visit Purposes
    VISIT_PURPOSES = [
        'Admission Inquiry',
        'Meeting',
        'Interview',
        'Guest Lecture',
        'Parent Meeting',
        'Official Work',
        'Delivery',
        'Training',
        'Event Participation',
        'Seminar',
        'Workshop',
        'Research Collaboration',
        'Alumni Visit',
        'Industry Visit',
        'Other'
    ]
    
    # ID Types
    ID_TYPES = [
        'Aadhar Card',
        'Driving License',
        'Passport',
        'Voter ID',
        'PAN Card',
        'College ID',
        'Student ID',
        'Employee ID',
        'Other'
    ]
    
    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', True)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@kprcollege.ac.in'
    
    # Application Settings
    COLLEGE_NAME = 'KPR College'
    COLLEGE_CODE = 'KPR'
    SYSTEM_TITLE = 'Visitor Management System'
    
    # Report Settings
    REPORT_EXPORT_FORMATS = ['csv', 'pdf', 'excel']


# Development Configuration
class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    SQLALCHEMY_ECHO = True
    LOG_LEVEL = 'DEBUG'


# Testing Configuration
class TestingConfig(Config):
    """Testing environment configuration"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key-do-not-use-in-production'


# Production Configuration
class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    LOG_LEVEL = 'WARNING'
    
    # Ensure SECRET_KEY is set in production
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError('SECRET_KEY environment variable must be set in production')


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """
    Get configuration based on environment
    
    Args:
        env (str): Environment name (development, testing, production)
        
    Returns:
        Config: Configuration class for the specified environment
    """
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development')
    
    return config.get(env, config['default'])
