# app.py - Complete Flask Application for KPR College Visitor Management System
# POSTGRESQL VERSION - With all vehicle, student, and parent fields

import os
import sys
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode
from io import BytesIO
import base64
import json
from sqlalchemy import inspect, text, func
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import csv
import pytz
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Timezone configuration
IST = pytz.timezone('Asia/Kolkata')

def get_indian_time():
    """Get current time in Indian Standard Time (IST) as naive datetime for database storage"""
    return datetime.now(IST).replace(tzinfo=None)

def get_indian_time_display():
    """Get current time in Indian Standard Time (IST) as timezone-aware for display"""
    return datetime.now(IST)

def indian_time_default():
    """Default function for SQLAlchemy datetime columns"""
    return get_indian_time()

# Get the absolute path of the current directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
logger.info(f"📁 Base directory: {BASE_DIR}")

# Set template and static folders
template_folder = os.path.join(BASE_DIR, 'templates')
static_folder = os.path.join(BASE_DIR, 'static')

# Verify template folder exists
if os.path.exists(template_folder):
    logger.info(f"✅ Templates folder found at: {template_folder}")
    template_files = os.listdir(template_folder)
    logger.info(f"📄 Template files: {', '.join(template_files[:5])}...")
else:
    logger.error(f"❌ Templates folder NOT found at: {template_folder}")
    # Try to create it
    os.makedirs(template_folder, exist_ok=True)
    logger.info(f"✅ Created templates folder at: {template_folder}")

# Initialize Flask App with correct paths
app = Flask(__name__,
            template_folder=template_folder,
            static_folder=static_folder)

logger.info(f"🚀 Flask app initialized")
logger.info(f"   Template folder: {app.template_folder}")
logger.info(f"   Static folder: {app.static_folder}")

# Configuration
class Config:
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        SECRET_KEY = 'kpr-college-secret-key-2024-dev'
        if os.environ.get('RENDER') == 'true':
            logger.warning("⚠️ Using default SECRET_KEY in production! Set SECRET_KEY environment variable.")
    
    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    if not SQLALCHEMY_DATABASE_URI:
        DB_USERNAME = os.environ.get('DB_USERNAME', 'postgres')
        DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')
        DB_HOST = os.environ.get('DB_HOST', 'localhost')
        DB_PORT = os.environ.get('DB_PORT', '5432')
        DB_NAME = os.environ.get('DB_NAME', 'kpr_visitor')
        SQLALCHEMY_DATABASE_URI = f'postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    
    # Handle Render.com's DATABASE_URL format
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
        logger.info("🔄 Converted postgres:// to postgresql://")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Connection pool settings for PostgreSQL
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'max_overflow': 10,
    }
    
    # Default credentials
    DEFAULT_ADMIN_USERNAME = os.environ.get('DEFAULT_ADMIN_USERNAME', 'admin')
    DEFAULT_ADMIN_PASSWORD = os.environ.get('DEFAULT_ADMIN_PASSWORD', 'admin')
    DEFAULT_SECURITY_USERNAME = os.environ.get('DEFAULT_SECURITY_USERNAME', 'security')
    DEFAULT_SECURITY_PASSWORD = os.environ.get('DEFAULT_SECURITY_PASSWORD', 'security123')
    
    # Upload configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp/uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # College departments
    DEPARTMENTS = [
        'Administration', 'Computer Science', 'Mathematics', 'Physics',
        'Chemistry', 'Biology', 'Commerce', 'Business Administration',
        'English', 'Tamil', 'Library', 'Sports', 'Examination Cell',
        'Placement Cell', 'Hostel', 'Accounts', 'Transport', 'Security',
        'Cafeteria', 'Maintenance'
    ]
    
    # Visit purposes
    VISIT_PURPOSES = [
        'Admission Inquiry', 'Meeting', 'Interview', 'Guest Lecture',
        'Parent Meeting', 'Official Work', 'Delivery', 'Training',
        'Event Participation', 'Seminar', 'Workshop', 'Research Collaboration',
        'Alumni Visit', 'Industry Visit', 'Other'
    ]
    
    # ID Types
    ID_TYPES = [
        'Aadhar Card', 'Driving License', 'Passport', 'Voter ID',
        'PAN Card', 'College ID', 'Student ID', 'Employee ID', 'Other'
    ]
    
    # Vehicle Types
    VEHICLE_TYPES = [
        'Two Wheeler', 'Four Wheeler', 'Auto Rickshaw', 'Van',
        'Bus', 'Truck', 'Other'
    ]

app.config.from_object(Config)

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
logger.info(f"📁 Upload folder: {app.config['UPLOAD_FOLDER']}")

# Initialize Extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

# Add custom Jinja2 filters
from markupsafe import escape

def escapejs(value):
    """Escape a string for use in JavaScript"""
    if value is None:
        return ''
    return escape(str(value)).replace("'", "\\'").replace('"', '\\"')

app.jinja_env.filters['escapejs'] = escapejs

# Inject current datetime and helper functions into all templates
@app.context_processor
def inject_now():
    return {
        'now': get_indian_time(),
        'now_display': get_indian_time_display(),
        'is_overdue': is_overdue,
        'vehicle_types': Config.VEHICLE_TYPES,
        'departments': Config.DEPARTMENTS,
        'purposes': Config.VISIT_PURPOSES,
        'id_types': Config.ID_TYPES
    }

# ===================== MODELS =====================
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(100))
    department = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=indian_time_default)
    updated_at = db.Column(db.DateTime, default=indian_time_default, onupdate=indian_time_default)

    def set_password(self, password):
        self.password_hash = password

    def check_password(self, password):
        return self.password_hash == password

    def update_last_login(self):
        self.last_login = get_indian_time()
        db.session.commit()

class IDCard(db.Model):
    __tablename__ = 'id_card'
    
    id = db.Column(db.Integer, primary_key=True)
    card_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), default='available')  # available, issued, lost, damaged
    issued_date = db.Column(db.DateTime)
    returned_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=indian_time_default)
    updated_at = db.Column(db.DateTime, default=indian_time_default, onupdate=indian_time_default)
    
    visitors = db.relationship('Visitor', backref='id_card_info', lazy='dynamic', foreign_keys='Visitor.card_id')
    
    def __repr__(self):
        return f'<IDCard {self.card_number} - {self.status}>'

class Visitor(db.Model):
    __tablename__ = 'visitor'
    
    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))  # Optional
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pincode = db.Column(db.String(10))
    
    # Identification
    id_type = db.Column(db.String(50))
    id_number = db.Column(db.String(100))
    id_photo = db.Column(db.String(200))
    
    # Company/Organization
    company = db.Column(db.String(100))
    
    # Vehicle information
    vehicle_number = db.Column(db.String(50))
    vehicle_type = db.Column(db.String(50))
    accompanied_count = db.Column(db.Integer, default=0)
    
    # Student/parent information
    student_name = db.Column(db.String(100))
    parent_name = db.Column(db.String(100))
    student_roll = db.Column(db.String(50))
    
    # Visit details
    person_to_meet = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    purpose = db.Column(db.String(200), nullable=False)
    visit_type = db.Column(db.String(50), default='general')
    expected_duration = db.Column(db.Integer)
    visit_notes = db.Column(db.Text)
    
    # Timing
    checkin_time = db.Column(db.DateTime, nullable=False, default=indian_time_default)
    expected_checkout = db.Column(db.DateTime)
    actual_checkout = db.Column(db.DateTime)
    
    # Staff handling
    checkin_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    checkout_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Status
    status = db.Column(db.String(20), default='checked_in', index=True)
    checkout_notes = db.Column(db.Text)
    rating = db.Column(db.Integer)
    
    # ID Card
    card_id = db.Column(db.Integer, db.ForeignKey('id_card.id'))
    card_issued_date = db.Column(db.DateTime)
    card_returned_date = db.Column(db.DateTime)
    
    # System fields
    created_at = db.Column(db.DateTime, default=indian_time_default)
    updated_at = db.Column(db.DateTime, default=indian_time_default, onupdate=indian_time_default)
    
    # Relationships
    checkin_user = db.relationship('User', foreign_keys=[checkin_by], backref='checkins')
    checkout_user = db.relationship('User', foreign_keys=[checkout_by], backref='checkouts')
    
    @property
    def card(self):
        if self.card_id:
            return IDCard.query.get(self.card_id)
        return None
    
    @property
    def is_overdue(self):
        if self.status != 'checked_in' or not self.expected_duration:
            return False
        expected_checkout = self.checkin_time + timedelta(minutes=self.expected_duration)
        return get_indian_time() > expected_checkout
    
    @property
    def duration_display(self):
        end_time = self.actual_checkout or get_indian_time()
        duration = end_time - self.checkin_time
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    
    @property
    def has_vehicle(self):
        return bool(self.vehicle_number or self.vehicle_type or self.accompanied_count)
    
    @property
    def has_student_info(self):
        return bool(self.student_name or self.parent_name or self.student_roll)
    
    @property
    def visit_type_display(self):
        types = {
            'admission': 'Admission',
            'parent': 'Parent-Teacher Meeting',
            'official': 'Official Visit',
            'general': 'General Visit'
        }
        return types.get(self.visit_type, self.visit_type.title())

class Settings(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=indian_time_default, onupdate=indian_time_default)

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(100), nullable=False)
    table_name = db.Column(db.String(50))
    record_id = db.Column(db.Integer)
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=indian_time_default)

# ===================== HELPER FUNCTIONS =====================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_visitor_id():
    """Generate unique visitor ID"""
    timestamp = datetime.now().strftime('%y%m%d')
    last_visitor = Visitor.query.filter(Visitor.visitor_id.like(f'KPR{timestamp}%')).order_by(Visitor.id.desc()).first()
    
    if last_visitor:
        last_num = int(last_visitor.visitor_id[-4:])
        new_num = last_num + 1
    else:
        new_num = 1
    
    return f'KPR{timestamp}{new_num:04d}'

def calculate_duration(checkin_time, checkout_time=None):
    """Calculate duration between checkin and checkout"""
    if not checkout_time:
        checkout_time = get_indian_time()
    
    duration = checkout_time - checkin_time
    total_minutes = int(duration.total_seconds() / 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    
    return {
        'hours': hours,
        'minutes': minutes,
        'total_minutes': total_minutes,
        'formatted': f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
    }

def is_overdue(checkin_time, expected_duration_minutes):
    """Check if visitor is overdue"""
    if not expected_duration_minutes:
        return False
    
    expected_checkout = checkin_time + timedelta(minutes=expected_duration_minutes)
    return get_indian_time() > expected_checkout

def get_status_text(checkin_time, expected_duration_minutes):
    """Get status text for visitor"""
    if not expected_duration_minutes:
        return "No time limit"
    
    expected_checkout = checkin_time + timedelta(minutes=expected_duration_minutes)
    now = get_indian_time()
    
    if now > expected_checkout:
        overdue_minutes = int((now - expected_checkout).total_seconds() / 60)
        return f"Overdue by {overdue_minutes} minutes"
    else:
        remaining_minutes = int((expected_checkout - now).total_seconds() / 60)
        return f"{remaining_minutes} minutes remaining"

def create_qr_code(data):
    """Create QR code from data"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def log_audit(action, table_name=None, record_id=None, old_value=None, new_value=None):
    """Log audit trail"""
    if not current_user.is_authenticated:
        return
    
    log = AuditLog(
        user_id=current_user.id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_value=str(old_value) if old_value else None,
        new_value=str(new_value) if new_value else None,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string if request.user_agent else None
    )
    db.session.add(log)
    db.session.commit()

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def initialize_id_cards():
    """Initialize ID cards CAS001-CAS100 if they don't exist"""
    try:
        existing = IDCard.query.count()
        if existing == 0:
            logger.info("Initializing ID cards CAS001-CAS100...")
            cards = []
            for i in range(1, 101):
                card = IDCard(
                    card_number=f'CAS{i:03d}',
                    status='available'
                )
                cards.append(card)
            
            db.session.bulk_save_objects(cards)
            db.session.commit()
            logger.info("✅ Created 100 ID cards (CAS001-CAS100)")
        else:
            logger.info(f"✅ ID cards already exist ({existing} cards)")
    except Exception as e:
        logger.error(f"❌ Could not initialize ID cards: {e}")
        db.session.rollback()

def get_available_id_card():
    """Get the first available ID card (lowest number)"""
    return IDCard.query.filter_by(status='available').order_by(IDCard.card_number).first()

def issue_id_card(visitor):
    """Issue an available ID card to a visitor"""
    card = get_available_id_card()
    if card:
        try:
            card.status = 'issued'
            card.issued_date = get_indian_time()
            card.returned_date = None
            
            visitor.card_id = card.id
            visitor.card_issued_date = get_indian_time()
            visitor.card_returned_date = None
            
            db.session.commit()
            logger.info(f"✅ Issued card {card.card_number} to visitor {visitor.visitor_id}")
            return card
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error issuing card: {e}")
            return None
    return None

def return_id_card(visitor):
    """Return the ID card from a visitor"""
    if visitor.card_id:
        try:
            card = IDCard.query.get(visitor.card_id)
            if card:
                card.status = 'available'
                card.returned_date = get_indian_time()
                
                visitor.card_returned_date = get_indian_time()
                
                db.session.commit()
                logger.info(f"✅ Returned card {card.card_number} from visitor {visitor.visitor_id}")
                return card
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Error returning card: {e}")
    return None

def upgrade_database():
    """Add new columns if they don't exist - PostgreSQL version"""
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'visitor' in tables:
                columns = [col['name'] for col in inspector.get_columns('visitor')]
                
                # Columns to add with PostgreSQL syntax
                columns_to_check = {
                    'vehicle_number': 'VARCHAR(50)',
                    'vehicle_type': 'VARCHAR(50)',
                    'accompanied_count': 'INTEGER DEFAULT 0',
                    'student_name': 'VARCHAR(100)',
                    'parent_name': 'VARCHAR(100)',
                    'student_roll': 'VARCHAR(50)',
                    'visit_type': 'VARCHAR(50) DEFAULT \'general\'',
                    'email': 'VARCHAR(120)'  # Add email back if needed
                }
                
                for col_name, col_type in columns_to_check.items():
                    if col_name not in columns:
                        try:
                            alter_stmt = f'ALTER TABLE visitor ADD COLUMN IF NOT EXISTS {col_name} {col_type}'
                            db.session.execute(text(alter_stmt))
                            db.session.commit()
                            logger.info(f"✅ Added {col_name} column")
                        except Exception as e:
                            logger.error(f"❌ Could not add {col_name}: {e}")
                            db.session.rollback()
            
            logger.info("✅ Database upgrade completed")
        except Exception as e:
            logger.error(f"❌ Database upgrade failed: {e}")

def date_range_filter(query, field, start_date, end_date):
    """Apply date range filter for PostgreSQL"""
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(field >= start)
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(field < end)
        except ValueError:
            pass
    return query

# ===================== ROUTES =====================
@app.route('/')
def home():
    """Home page - redirect to login or dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        user = User.query.filter_by(username=username, is_active=True).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            user.update_last_login()
            log_audit('login')
            
            flash(f'Welcome back, {user.full_name or user.username}!', 'success')
            
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('security_dashboard'))
        else:
            flash('Invalid username or password', 'error')
            log_audit('failed_login', old_value=username)
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    log_audit('logout')
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page - redirects based on role"""
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('security_dashboard'))

@app.route('/visitors')
@login_required
def visitors():
    """Visitors page - redirects based on role"""
    if current_user.is_admin:
        return redirect(url_for('admin_visitors'))
    else:
        return redirect(url_for('security_visitors'))

@app.route('/id-cards')
@app.route('/idcards')
@login_required
def id_cards():
    """ID Cards page - redirects based on role"""
    args = request.args.to_dict()
    if current_user.is_admin:
        return redirect(url_for('admin_idcards', **args))
    else:
        return redirect(url_for('security_idcards', **args))

@app.route('/reports')
@login_required
def reports():
    """Reports page - redirects based on role"""
    if current_user.is_admin:
        return redirect(url_for('admin_reports'))
    else:
        flash('Access denied. Reports are only available to admins.', 'warning')
        return redirect(url_for('security_dashboard'))

# ===================== ADMIN ROUTES =====================
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin Dashboard"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_dashboard'))
    
    now = get_indian_time()
    today_start = datetime(now.year, now.month, now.day)
    today_end = today_start + timedelta(days=1)
    
    # Statistics
    total_visitors_today = Visitor.query.filter(Visitor.checkin_time >= today_start).count()
    active_visitors = Visitor.query.filter_by(status='checked_in').count()
    total_visitors = Visitor.query.count()
    
    # ID Card Statistics
    available_cards = IDCard.query.filter_by(status='available').count()
    issued_cards = IDCard.query.filter_by(status='issued').count()
    lost_cards = IDCard.query.filter_by(status='lost').count()
    damaged_cards = IDCard.query.filter_by(status='damaged').count()
    
    # Recent visitors
    recent_visitors = Visitor.query.order_by(Visitor.checkin_time.desc()).limit(10).all()
    
    # Add card info to recent visitors
    for visitor in recent_visitors:
        if visitor.card_id:
            visitor.card_info = IDCard.query.get(visitor.card_id)
    
    # Department-wise distribution
    dept_stats = db.session.query(
        Visitor.department,
        func.count(Visitor.id).label('count')
    ).filter(Visitor.checkin_time >= today_start).group_by(Visitor.department).all()
    
    # Overdue visitors
    overdue_count = 0
    for visitor in Visitor.query.filter_by(status='checked_in').all():
        if visitor.expected_duration and is_overdue(visitor.checkin_time, visitor.expected_duration):
            overdue_count += 1
    
    # Card usage
    card_usage = {
        'total': 100,
        'available': available_cards,
        'issued': issued_cards,
        'utilization': round((issued_cards / 100) * 100, 1) if issued_cards else 0
    }
    
    # Today's checkout count
    checked_out_today = Visitor.query.filter(
        Visitor.actual_checkout >= today_start,
        Visitor.actual_checkout < today_end
    ).count()
    
    return render_template('admin_dashboard.html',
                         now=now,
                         total_visitors_today=total_visitors_today,
                         visitors_checked_in=active_visitors,
                         total_visitors=total_visitors,
                         checked_out_today=checked_out_today,
                         available_cards=available_cards,
                         issued_cards=issued_cards,
                         lost_cards=lost_cards,
                         damaged_cards=damaged_cards,
                         recent_visitors=recent_visitors,
                         dept_stats=dept_stats,
                         overdue_count=overdue_count,
                         card_usage=card_usage)

@app.route('/admin/visitors')
@login_required
def admin_visitors():
    """Admin Visitor Management"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_visitors'))
    
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    date_filter = request.args.get('date', '')
    department_filter = request.args.get('department', 'all')
    search_query = request.args.get('search', '')
    has_card_filter = request.args.get('has_card', 'all')
    visit_type_filter = request.args.get('visit_type', 'all')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = Visitor.query
    
    # Apply filters
    if status_filter == 'checked_in':
        query = query.filter_by(status='checked_in')
    elif status_filter == 'checked_out':
        query = query.filter_by(status='checked_out')
    
    if has_card_filter == 'yes':
        query = query.filter(Visitor.card_id.isnot(None))
    elif has_card_filter == 'no':
        query = query.filter(Visitor.card_id.is_(None))
    
    # Date range filter
    query = date_range_filter(query, Visitor.checkin_time, start_date, end_date)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(func.cast(Visitor.checkin_time, db.Date) == filter_date)
        except ValueError:
            pass
    
    if department_filter != 'all':
        query = query.filter_by(department=department_filter)
    
    if visit_type_filter != 'all':
        query = query.filter_by(visit_type=visit_type_filter)
    
    if search_query:
        search = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Visitor.visitor_id.ilike(search),
                Visitor.full_name.ilike(search),
                Visitor.phone.ilike(search),
                Visitor.person_to_meet.ilike(search),
                Visitor.vehicle_number.ilike(search),
                Visitor.student_name.ilike(search),
                Visitor.parent_name.ilike(search)
            )
        )
    
    # Pagination
    pagination = query.order_by(Visitor.checkin_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    visitors = pagination.items
    
    # Calculate additional data for each visitor
    for visitor in visitors:
        if visitor.status == 'checked_in':
            visitor.current_duration = calculate_duration(visitor.checkin_time)
            visitor.is_overdue_flag = is_overdue(visitor.checkin_time, visitor.expected_duration)
        elif visitor.actual_checkout:
            visitor.total_duration = calculate_duration(visitor.checkin_time, visitor.actual_checkout)
        if visitor.card_id:
            visitor.card_info = IDCard.query.get(visitor.card_id)
    
    # Statistics
    active_visitors = Visitor.query.filter_by(status='checked_in').count()
    today_start = get_indian_time().replace(hour=0, minute=0, second=0)
    checked_out_today = Visitor.query.filter(Visitor.actual_checkout >= today_start).count()
    
    return render_template('admin_visitors.html',
                         visitors=visitors,
                         pagination=pagination,
                         active_visitors=active_visitors,
                         checked_out_today=checked_out_today,
                         status_filter=status_filter,
                         date_filter=date_filter,
                         department_filter=department_filter,
                         has_card_filter=has_card_filter,
                         search_query=search_query,
                         visit_type_filter=visit_type_filter,
                         start_date=start_date,
                         end_date=end_date,
                         page=page)

@app.route('/admin/visitor/<visitor_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_visitor(visitor_id):
    """Admin Edit Visitor Details"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_visitors'))
    
    visitor = Visitor.query.filter_by(visitor_id=visitor_id).first_or_404()
    
    if request.method == 'POST':
        try:
            # Update visitor details
            visitor.full_name = request.form.get('full_name', visitor.full_name)
            visitor.phone = request.form.get('phone', visitor.phone)
            visitor.email = request.form.get('email', visitor.email)
            visitor.address = request.form.get('address', visitor.address)
            visitor.city = request.form.get('city', visitor.city)
            visitor.state = request.form.get('state', visitor.state)
            visitor.pincode = request.form.get('pincode', visitor.pincode)
            visitor.id_type = request.form.get('id_type', visitor.id_type)
            visitor.id_number = request.form.get('id_number', visitor.id_number)
            visitor.company = request.form.get('company', visitor.company)
            visitor.person_to_meet = request.form.get('person_to_meet', visitor.person_to_meet)
            visitor.department = request.form.get('department', visitor.department)
            visitor.purpose = request.form.get('purpose', visitor.purpose)
            visitor.visit_notes = request.form.get('visit_notes', visitor.visit_notes)
            
            # Vehicle info
            visitor.vehicle_number = request.form.get('vehicle_number', visitor.vehicle_number)
            visitor.vehicle_type = request.form.get('vehicle_type', visitor.vehicle_type)
            accompanied = request.form.get('accompanied_count')
            if accompanied and accompanied.isdigit():
                visitor.accompanied_count = int(accompanied)
            
            # Student info
            visitor.student_name = request.form.get('student_name', visitor.student_name)
            visitor.parent_name = request.form.get('parent_name', visitor.parent_name)
            visitor.student_roll = request.form.get('student_roll', visitor.student_roll)
            
            db.session.commit()
            log_audit('visitor_updated', 'Visitor', visitor.id)
            
            flash('Visitor details updated successfully!', 'success')
            return redirect(url_for('visitor_details', visitor_id=visitor.visitor_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating visitor: {str(e)}', 'error')
            logger.error(f"Update error: {e}")
    
    card = visitor.card if visitor.card_id else None
    
    return render_template('admin_edit_visitor.html',
                         visitor=visitor,
                         card=card)

@app.route('/admin/idcards')
@login_required
def admin_idcards():
    """Admin ID Card Management"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_idcards'))
    
    # Statistics
    available_count = IDCard.query.filter_by(status='available').count()
    issued_count = IDCard.query.filter_by(status='issued').count()
    lost_count = IDCard.query.filter_by(status='lost').count()
    damaged_count = IDCard.query.filter_by(status='damaged').count()
    total_count = IDCard.query.count()
    
    # Filters
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = IDCard.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if search_query:
        query = query.filter(IDCard.card_number.ilike(f'%{search_query}%'))
    
    pagination = query.order_by(IDCard.card_number).paginate(
        page=page, per_page=per_page, error_out=False
    )
    cards = pagination.items
    
    # Prepare card data with current visitor
    card_data = []
    for card in cards:
        current_visitor = None
        if card.status == 'issued':
            current_visitor = Visitor.query.filter_by(
                card_id=card.id,
                status='checked_in'
            ).first()
        
        card_data.append({
            'card': card,
            'current_visitor': current_visitor
        })
    
    return render_template('admin_idcards.html',
                         cards=card_data,
                         pagination=pagination,
                         available_count=available_count,
                         issued_count=issued_count,
                         lost_count=lost_count,
                         damaged_count=damaged_count,
                         total_count=total_count,
                         status_filter=status_filter,
                         search_query=search_query)

@app.route('/admin/reports')
@login_required
def admin_reports():
    """Enhanced Reports page"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_dashboard'))
    
    # Get filter parameters
    report_type = request.args.get('type', 'daily')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    department = request.args.get('department', '')
    visit_type = request.args.get('visit_type', '')
    
    query = Visitor.query
    
    # Apply date filters
    query = date_range_filter(query, Visitor.checkin_time, start_date, end_date)
    
    # Default date ranges
    if not start_date and not end_date:
        now = get_indian_time()
        if report_type == 'daily':
            query = query.filter(func.cast(Visitor.checkin_time, db.Date) == now.date())
            title = f"Daily Report - {now.strftime('%d/%m/%Y')}"
        elif report_type == 'weekly':
            week_ago = now - timedelta(days=7)
            query = query.filter(Visitor.checkin_time >= week_ago)
            title = "Weekly Report (Last 7 Days)"
        elif report_type == 'monthly':
            month_ago = now - timedelta(days=30)
            query = query.filter(Visitor.checkin_time >= month_ago)
            title = "Monthly Report (Last 30 Days)"
        else:
            title = "Complete Report"
    else:
        date_range = []
        if start_date:
            date_range.append(f"from {start_date}")
        if end_date:
            date_range.append(f"to {end_date}")
        title = f"Report {' '.join(date_range)}"
    
    # Apply other filters
    if department:
        query = query.filter_by(department=department)
    if visit_type:
        query = query.filter_by(visit_type=visit_type)
    
    visitors = query.order_by(Visitor.checkin_time.desc()).all()
    
    # Statistics
    total_visitors = len(visitors)
    checked_in_count = len([v for v in visitors if v.status == 'checked_in'])
    checked_out_count = len([v for v in visitors if v.status == 'checked_out'])
    cards_issued_count = len([v for v in visitors if v.card_id])
    
    # Department stats
    dept_stats = {}
    for visitor in visitors:
        dept_stats[visitor.department] = dept_stats.get(visitor.department, 0) + 1
    
    # Purpose stats
    purpose_stats = {}
    for visitor in visitors:
        purpose_stats[visitor.purpose] = purpose_stats.get(visitor.purpose, 0) + 1
    
    # Vehicle stats
    vehicle_count = len([v for v in visitors if v.vehicle_number])
    
    # Student stats
    student_visits = len([v for v in visitors if v.student_name])
    parent_visits = len([v for v in visitors if v.parent_name])
    
    return render_template('admin_reports.html',
                         visitors=visitors,
                         total_visitors=total_visitors,
                         checked_in_count=checked_in_count,
                         checked_out_count=checked_out_count,
                         cards_issued_count=cards_issued_count,
                         dept_stats=dept_stats,
                         purpose_stats=purpose_stats,
                         vehicle_count=vehicle_count,
                         student_visits=student_visits,
                         parent_visits=parent_visits,
                         title=title,
                         start_date=start_date,
                         end_date=end_date,
                         department_filter=department,
                         visit_type_filter=visit_type,
                         report_type=report_type)

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    """Settings page"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_dashboard'))

    if request.method == 'POST':
        # Update settings
        for key, value in request.form.items():
            if key.startswith('setting_'):
                real_key = key[8:]
                setting = Settings.query.filter_by(key=real_key).first()
                if setting:
                    setting.value = value
                else:
                    setting = Settings(key=real_key, value=value)
                    db.session.add(setting)
        
        db.session.commit()
        flash('Settings updated successfully.', 'success')
        return redirect(url_for('admin_settings'))

    all_settings = Settings.query.all()
    settings_dict = {s.key: s.value for s in all_settings}
    
    return render_template('admin_settings.html',
                         settings=settings_dict)

# ===================== SECURITY ROUTES =====================
@app.route('/security/dashboard')
@login_required
def security_dashboard():
    """Security Dashboard"""
    now = get_indian_time()
    today_start = datetime(now.year, now.month, now.day)
    
    # Statistics
    active_visitors = Visitor.query.filter_by(status='checked_in').count()
    total_visitors_today = Visitor.query.filter(Visitor.checkin_time >= today_start).count()
    available_cards = IDCard.query.filter_by(status='available').count()
    
    # Checked out today
    checked_out_today = Visitor.query.filter(
        Visitor.actual_checkout >= today_start
    ).count()
    
    # Active visitors list
    active_visitors_list = Visitor.query.filter_by(status='checked_in')\
        .order_by(Visitor.checkin_time.desc()).limit(10).all()
    
    for visitor in active_visitors_list:
        visitor.is_overdue_flag = is_overdue(visitor.checkin_time, visitor.expected_duration)
        if visitor.card_id:
            visitor.card_info = IDCard.query.get(visitor.card_id)
    
    # Recent checkouts
    recent_checkouts = Visitor.query.filter(
        Visitor.actual_checkout.isnot(None)
    ).order_by(Visitor.actual_checkout.desc()).limit(5).all()
    
    # Overdue count
    overdue_count = 0
    for visitor in Visitor.query.filter_by(status='checked_in').all():
        if visitor.expected_duration and is_overdue(visitor.checkin_time, visitor.expected_duration):
            overdue_count += 1
    
    return render_template('security_dashboard.html',
                         now=now,
                         active_visitors=active_visitors,
                         total_visitors_today=total_visitors_today,
                         checked_out_today=checked_out_today,
                         available_cards=available_cards,
                         active_visitors_list=active_visitors_list,
                         recent_checkouts=recent_checkouts,
                         overdue_count=overdue_count)

@app.route('/security/visitors')
@login_required
def security_visitors():
    """Security Visitor Management"""
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = Visitor.query
    
    # Apply filters
    if status_filter == 'checked_in':
        query = query.filter_by(status='checked_in')
    elif status_filter == 'checked_out':
        query = query.filter_by(status='checked_out')
    
    query = date_range_filter(query, Visitor.checkin_time, start_date, end_date)
    
    if search_query:
        search = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Visitor.visitor_id.ilike(search),
                Visitor.full_name.ilike(search),
                Visitor.phone.ilike(search)
            )
        )
    
    pagination = query.order_by(Visitor.checkin_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    visitors = pagination.items
    
    for visitor in visitors:
        if visitor.status == 'checked_in':
            visitor.current_duration = calculate_duration(visitor.checkin_time)
            visitor.is_overdue_flag = is_overdue(visitor.checkin_time, visitor.expected_duration)
        if visitor.card_id:
            visitor.card_info = IDCard.query.get(visitor.card_id)
    
    return render_template('security_visitors.html',
                         visitors=visitors,
                         pagination=pagination,
                         status_filter=status_filter,
                         search_query=search_query,
                         start_date=start_date,
                         end_date=end_date)

@app.route('/security/idcards')
@login_required
def security_idcards():
    """Security ID Card Management"""
    # Statistics
    available_count = IDCard.query.filter_by(status='available').count()
    issued_count = IDCard.query.filter_by(status='issued').count()
    
    # Filters
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = IDCard.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if search_query:
        query = query.filter(IDCard.card_number.ilike(f'%{search_query}%'))
    
    pagination = query.order_by(IDCard.card_number).paginate(
        page=page, per_page=per_page, error_out=False
    )
    cards = pagination.items
    
    # Prepare card data
    card_data = []
    for card in cards:
        current_visitor = None
        if card.status == 'issued':
            current_visitor = Visitor.query.filter_by(
                card_id=card.id,
                status='checked_in'
            ).first()
        
        card_data.append({
            'card': card,
            'current_visitor': current_visitor
        })
    
    return render_template('security_idcards.html',
                         cards=card_data,
                         pagination=pagination,
                         available_count=available_count,
                         issued_count=issued_count,
                         status_filter=status_filter,
                         search_query=search_query)

# ===================== SHARED ROUTES =====================
@app.route('/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    """Visitor check-in page"""
    if request.method == 'POST':
        try:
            visitor_id = generate_visitor_id()
            
            # Parse expected duration
            expected_duration = request.form.get('expected_duration')
            if expected_duration and expected_duration.isdigit():
                expected_duration = int(expected_duration)
                expected_checkout = get_indian_time() + timedelta(minutes=expected_duration)
            else:
                expected_duration = None
                expected_checkout = None
            
            # Determine visit type
            visit_type = request.form.get('visit_type', 'general').lower()
            
            # Create visitor
            visitor = Visitor(
                visitor_id=visitor_id,
                full_name=request.form.get('full_name', '').strip(),
                phone=request.form.get('phone', '').strip(),
                email=request.form.get('email', '').strip(),
                address=request.form.get('address', '').strip(),
                city=request.form.get('city', '').strip(),
                state=request.form.get('state', '').strip(),
                pincode=request.form.get('pincode', '').strip(),
                id_type=request.form.get('id_type', ''),
                id_number=request.form.get('id_number', '').strip(),
                company=request.form.get('company', '').strip(),
                person_to_meet=request.form.get('person_to_meet', '').strip(),
                department=request.form.get('department', 'Administration'),
                purpose=request.form.get('purpose', '').strip(),
                visit_type=visit_type,
                expected_duration=expected_duration,
                expected_checkout=expected_checkout,
                visit_notes=request.form.get('visit_notes', '').strip(),
                student_name=request.form.get('student_name', '').strip(),
                parent_name=request.form.get('parent_name', '').strip(),
                student_roll=request.form.get('student_roll', '').strip(),
                vehicle_number=request.form.get('vehicle_number', '').strip(),
                vehicle_type=request.form.get('vehicle_type', '').strip(),
                accompanied_count=int(request.form.get('accompanied_count') or 0),
                checkin_by=current_user.id,
                status='checked_in'
            )
            
            # Handle photo upload
            if 'id_photo' in request.files:
                file = request.files['id_photo']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(f"{visitor_id}_{file.filename}")
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    visitor.id_photo = filename
            
            db.session.add(visitor)
            db.session.commit()
            
            # Issue ID card
            card = issue_id_card(visitor)
            
            # Generate QR code
            qr_data = f"Visitor ID: {visitor_id}\nName: {visitor.full_name}\nCheck-in: {visitor.checkin_time.strftime('%Y-%m-%d %H:%M')}"
            if card:
                qr_data += f"\nCard: {card.card_number}"
            
            qr_code = create_qr_code(qr_data)
            
            log_audit('visitor_checkin', 'Visitor', visitor.id)
            
            flash(f'Visitor {visitor.full_name} checked in successfully!', 'success')
            
            return render_template('checkin_success.html',
                                 visitor=visitor,
                                 qr_code=qr_code,
                                 card=card)
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error checking in visitor: {str(e)}', 'error')
            logger.error(f"Check-in error: {e}")
    
    # GET request
    available_cards_count = IDCard.query.filter_by(status='available').count()
    
    return render_template('checkin.html',
                         available_cards=available_cards_count,
                         now=get_indian_time_display())

@app.route('/checkout', methods=['GET', 'POST'])
@app.route('/checkout_page', methods=['GET', 'POST'], endpoint='checkout_page')
@login_required
def checkout():
    """Visitor check-out page"""
    if request.method == 'POST':
        visitor_id = request.form.get('visitor_id')
        checkout_notes = request.form.get('checkout_notes', '')
        rating = request.form.get('rating')
        
        visitor = Visitor.query.filter_by(visitor_id=visitor_id, status='checked_in').first()
        
        if visitor:
            try:
                visitor.actual_checkout = get_indian_time()
                visitor.checkout_by = current_user.id
                visitor.status = 'checked_out'
                visitor.checkout_notes = checkout_notes
                if rating and rating.isdigit():
                    visitor.rating = int(rating)
                
                duration = calculate_duration(visitor.checkin_time, visitor.actual_checkout)
                
                # Return ID card
                card = None
                if visitor.card_id:
                    card = return_id_card(visitor)
                
                db.session.commit()
                
                log_audit('visitor_checkout', 'Visitor', visitor.id)
                
                flash(f'Visitor {visitor.full_name} checked out successfully!', 'success')
                
                return render_template('checkout_success.html',
                                     visitor=visitor,
                                     duration=duration,
                                     card=card)
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error checking out visitor: {str(e)}', 'error')
                logger.error(f"Checkout error: {e}")
        else:
            flash('Visitor not found or already checked out', 'error')
    
    # GET request
    active_visitors = Visitor.query.filter_by(status='checked_in')\
        .order_by(Visitor.checkin_time.desc()).all()
    
    for visitor in active_visitors:
        visitor.duration = calculate_duration(visitor.checkin_time)
        visitor.is_overdue_flag = is_overdue(visitor.checkin_time, visitor.expected_duration)
        visitor.status_text = get_status_text(visitor.checkin_time, visitor.expected_duration)
        if visitor.card_id:
            visitor.card_info = IDCard.query.get(visitor.card_id)
    
    return render_template('checkout.html',
                         active_visitors=active_visitors)

@app.route('/checkout_success')
@login_required
def checkout_success():
    """Checkout success page"""
    visitor_id = request.args.get('visitor_id', '')
    if not visitor_id:
        flash('Missing visitor ID.', 'error')
        return redirect(url_for('checkout_page'))
    
    visitor = Visitor.query.filter_by(visitor_id=visitor_id).first()
    if not visitor:
        flash('Visitor not found.', 'error')
        return redirect(url_for('checkout_page'))

    duration = calculate_duration(visitor.checkin_time, visitor.actual_checkout) if visitor.actual_checkout else None
    card = visitor.card if visitor.card_id else None

    return render_template('checkout_success.html',
                         visitor=visitor,
                         duration=duration,
                         card=card)

@app.route('/visitor/<visitor_id>')
@login_required
def visitor_details(visitor_id):
    """Visitor details page"""
    visitor = Visitor.query.filter_by(visitor_id=visitor_id).first_or_404()
    
    # Calculate durations
    if visitor.status == 'checked_in':
        duration = calculate_duration(visitor.checkin_time)
        is_overdue_flag = is_overdue(visitor.checkin_time, visitor.expected_duration)
    elif visitor.actual_checkout:
        duration = calculate_duration(visitor.checkin_time, visitor.actual_checkout)
        is_overdue_flag = False
    else:
        duration = None
        is_overdue_flag = False
    
    card = visitor.card if visitor.card_id else None
    
    # Get user details
    checkin_user = User.query.get(visitor.checkin_by) if visitor.checkin_by else None
    checkout_user = User.query.get(visitor.checkout_by) if visitor.checkout_by else None
    
    # Generate QR code if active
    qr_code = None
    if visitor.status == 'checked_in':
        qr_data = f"Visitor ID: {visitor.visitor_id}\nName: {visitor.full_name}\nCheck-in: {visitor.checkin_time.strftime('%Y-%m-%d %H:%M')}"
        if card:
            qr_data += f"\nCard: {card.card_number}"
        qr_code = create_qr_code(qr_data)
    
    return render_template('visitor_details.html',
                         visitor=visitor,
                         card=card,
                         duration=duration,
                         is_overdue=is_overdue_flag,
                         qr_code=qr_code,
                         checkin_user=checkin_user,
                         checkout_user=checkout_user)

@app.route('/idcard/<card_number>')
@login_required
def id_card_details(card_number):
    """ID card details page"""
    card = IDCard.query.filter_by(card_number=card_number).first_or_404()
    
    # Get current visitor
    current_visitor = None
    if card.status == 'issued':
        current_visitor = Visitor.query.filter_by(
            card_id=card.id,
            status='checked_in'
        ).first()
    
    # Get history
    history = Visitor.query.filter_by(card_id=card.id)\
        .order_by(Visitor.card_issued_date.desc()).limit(20).all()
    
    return render_template('idcard_details.html',
                         card=card,
                         current_visitor=current_visitor,
                         history=history)

@app.route('/notifications')
@login_required
def notifications():
    """Notifications page"""
    # Get overdue visitors
    active_visitors = Visitor.query.filter_by(status='checked_in').all()
    overdue_visitors = []
    
    for visitor in active_visitors:
        if is_overdue(visitor.checkin_time, visitor.expected_duration):
            time_exceeded = calculate_duration(visitor.checkin_time)['total_minutes'] - visitor.expected_duration
            overdue_visitors.append({
                'visitor': visitor,
                'duration_exceeded': time_exceeded
            })
    
    # ID card statistics
    available_cards = IDCard.query.filter_by(status='available').count()
    low_cards = available_cards < 5
    
    return render_template('notifications.html',
                         alerts=overdue_visitors,
                         available_cards=available_cards,
                         low_cards=low_cards)

# ===================== API ROUTES =====================
@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    try:
        db.session.execute(text('SELECT 1'))
        db_status = 'connected'
        
        # Check templates
        template_status = 'ok' if os.path.exists(app.template_folder) else 'missing'
        
        return jsonify({
            'status': 'healthy',
            'timestamp': get_indian_time_display().isoformat(),
            'database': db_status,
            'templates': template_status,
            'environment': os.environ.get('RENDER', 'development'),
            'version': '2.1.0-postgresql'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    """API endpoint for dashboard statistics"""
    try:
        now = get_indian_time()
        today_start = datetime(now.year, now.month, now.day)
        
        stats = {
            'visitors_today': Visitor.query.filter(Visitor.checkin_time >= today_start).count(),
            'active_visitors': Visitor.query.filter_by(status='checked_in').count(),
            'total_visitors': Visitor.query.count(),
            'available_cards': IDCard.query.filter_by(status='available').count(),
            'checked_out_today': Visitor.query.filter(Visitor.actual_checkout >= today_start).count()
        }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/visitors/active')
@login_required
def api_active_visitors():
    """API endpoint for active visitors"""
    visitors = Visitor.query.filter_by(status='checked_in')\
        .order_by(Visitor.checkin_time.desc()).all()
    
    data = []
    for v in visitors:
        data.append({
            'visitor_id': v.visitor_id,
            'name': v.full_name,
            'department': v.department,
            'checkin_time': v.checkin_time.isoformat(),
            'duration': calculate_duration(v.checkin_time)['formatted'],
            'is_overdue': is_overdue(v.checkin_time, v.expected_duration)
        })
    
    return jsonify(data)

# ===================== EXPORT ROUTES =====================
@app.route('/export/csv')
@login_required
def export_csv():
    """Export visitors data as CSV"""
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('security_dashboard'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    query = Visitor.query
    query = date_range_filter(query, Visitor.checkin_time, start_date, end_date)
    visitors = query.order_by(Visitor.checkin_time.desc()).all()
    
    # Create CSV
    output = BytesIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Visitor ID', 'Name', 'Phone', 'Email', 'ID Type', 'ID Number',
        'Vehicle Number', 'Vehicle Type', 'Student Name', 'Parent Name',
        'Person to Meet', 'Department', 'Purpose', 'Visit Type',
        'Check-in Time', 'Check-out Time', 'Status', 'ID Card'
    ])
    
    # Write data
    for v in visitors:
        card_number = v.card.card_number if v.card_id else ''
        
        writer.writerow([
            v.visitor_id, v.full_name, v.phone, v.email or '',
            v.id_type or '', v.id_number or '',
            v.vehicle_number or '', v.vehicle_type or '',
            v.student_name or '', v.parent_name or '',
            v.person_to_meet, v.department, v.purpose, v.visit_type,
            v.checkin_time.strftime('%Y-%m-%d %H:%M:%S'),
            v.actual_checkout.strftime('%Y-%m-%d %H:%M:%S') if v.actual_checkout else '',
            v.status, card_number
        ])
    
    output.seek(0)
    
    filename = f'visitors_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )

# ===================== ERROR HANDLERS =====================
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"500 error: {e}")
    return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

# ===================== INITIALIZATION =====================
def create_default_settings():
    """Create default settings"""
    default_settings = [
        ('college_name', 'KPR College of Arts Science and Research', 'College name'),
        ('college_address', 'Coimbatore, Tamil Nadu', 'College address'),
        ('college_phone', '+91 422 1234567', 'College phone number'),
        ('college_email', 'info@kprcollege.edu', 'College email'),
    ]
    
    for key, value, description in default_settings:
        setting = Settings.query.filter_by(key=key).first()
        if not setting:
            setting = Settings(key=key, value=value, description=description)
            db.session.add(setting)
    
    db.session.commit()
    logger.info("✅ Default settings created")

def create_default_users():
    """Create default users"""
    # Admin
    admin = User.query.filter_by(username=app.config['DEFAULT_ADMIN_USERNAME']).first()
    if not admin:
        admin = User(
            username=app.config['DEFAULT_ADMIN_USERNAME'],
            email='admin@kprcollege.edu',
            full_name='Administrator',
            department='Administration',
            phone='+91 9876543210',
            is_admin=True,
            is_active=True
        )
        admin.set_password(app.config['DEFAULT_ADMIN_PASSWORD'])
        db.session.add(admin)
        logger.info("✅ Default admin user created")
    
    # Security
    security = User.query.filter_by(username=app.config['DEFAULT_SECURITY_USERNAME']).first()
    if not security:
        security = User(
            username=app.config['DEFAULT_SECURITY_USERNAME'],
            email='security@kprcollege.edu',
            full_name='Security Officer',
            department='Security',
            phone='+91 9876543211',
            is_admin=False,
            is_active=True
        )
        security.set_password(app.config['DEFAULT_SECURITY_PASSWORD'])
        db.session.add(security)
        logger.info("✅ Default security user created")
    
    db.session.commit()

def init_database():
    """Initialize database"""
    with app.app_context():
        try:
            # Test connection
            db.session.execute(text('SELECT 1'))
            logger.info("✅ PostgreSQL connection successful")
            
            # Create tables
            db.create_all()
            logger.info("✅ Database tables created/verified")
            
            # Upgrade schema
            upgrade_database()
            
            # Initialize data
            initialize_id_cards()
            create_default_users()
            create_default_settings()
            
            logger.info("✅ Database initialization complete")
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            # Don't raise - allow app to start with limited functionality

# ===================== APPLICATION ENTRY POINT =====================
if __name__ != '__main__':
    # Running on Gunicorn
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    
    # Initialize database
    init_database()

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 KPR COLLEGE VISITOR MANAGEMENT SYSTEM")
    print("="*60)
    print(f"📁 Template folder: {app.template_folder}")
    print(f"📁 Static folder: {app.static_folder}")
    print(f"✅ Templates found: {os.path.exists(app.template_folder)}")
    print(f"✅ login.html exists: {os.path.exists(os.path.join(app.template_folder, 'login.html'))}")
    print(f"\n🌐 Server URL:  http://localhost:5000")
    print(f"👤 Admin Login:  admin / admin")
    print(f"👤 Security Login: security / security123")
    print("="*60)
    
    # Initialize database
    init_database()
    
    # Run the application
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
