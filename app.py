# app.py - Complete Flask Application for KPR College Visitor Management System
# POSTGRESQL VERSION - With all vehicle, student, and parent fields

import os
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
from sqlalchemy import inspect, text
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import csv
import pytz
from dotenv import load_dotenv

# Load environment variables from .env file
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

# Initialize Flask App
app = Flask(__name__, 
            template_folder='kpr-visitor-system/templates',
            static_folder='kpr-visitor-system/static')

# Configuration
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kpr-college-secret-key-2024'
    
    # PostgreSQL Configuration from environment variables
    DB_USERNAME = os.environ.get('DB_USERNAME', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'kpr_visitor')
    
    # PostgreSQL Connection String
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Connection pool settings for PostgreSQL
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
    
    # Default credentials
    DEFAULT_ADMIN_USERNAME = os.environ.get('DEFAULT_ADMIN_USERNAME', 'admin')
    DEFAULT_ADMIN_PASSWORD = os.environ.get('DEFAULT_ADMIN_PASSWORD', 'admin')
    DEFAULT_SECURITY_USERNAME = os.environ.get('DEFAULT_SECURITY_USERNAME', 'security')
    DEFAULT_SECURITY_PASSWORD = os.environ.get('DEFAULT_SECURITY_PASSWORD', 'security123')
    
    # College departments
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
    
    # Visit purposes
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
    
    # Vehicle Types
    VEHICLE_TYPES = [
        'Two Wheeler',
        'Four Wheeler',
        'Auto Rickshaw',
        'Van',
        'Bus',
        'Truck',
        'Other'
    ]
    
    # Upload configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

app.config.from_object(Config)

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

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Inject current datetime and helper functions into all templates
@app.context_processor
def inject_now():
    return {
        'now': get_indian_time(),
        'is_overdue': is_overdue,
        'vehicle_types': Config.VEHICLE_TYPES
    }

# ===================== MODELS =====================
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
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
        # store raw password directly
        self.password_hash = password

    def check_password(self, password):
        # compare raw values
        return self.password_hash == password

    def update_last_login(self):
        self.last_login = get_indian_time()
        db.session.commit()

class IDCard(db.Model):
    """Track physical ID cards (CAS001-CAS100) issued to visitors"""
    __tablename__ = 'id_card'
    
    id = db.Column(db.Integer, primary_key=True)
    card_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), default='available')  # available, issued, lost, damaged
    
    # Tracking dates
    issued_date = db.Column(db.DateTime)
    returned_date = db.Column(db.DateTime)
    
    # System fields
    created_at = db.Column(db.DateTime, default=indian_time_default)
    updated_at = db.Column(db.DateTime, default=indian_time_default, onupdate=indian_time_default)
    
    # Relationship - one card can be used by multiple visitors over time
    visitors = db.relationship('Visitor', backref='id_card_info', lazy='dynamic', foreign_keys='Visitor.card_id')
    
    def __repr__(self):
        return f'<IDCard {self.card_number} - {self.status}>'

class Visitor(db.Model):
    __tablename__ = 'visitor'
    
    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
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
    
    # Student/parent information (for admissions and parent meetings)
    student_name = db.Column(db.String(100))
    parent_name = db.Column(db.String(100))
    student_roll = db.Column(db.String(50))
    
    # Visit details
    person_to_meet = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    purpose = db.Column(db.String(200), nullable=False)
    visit_type = db.Column(db.String(50), default='general')  # admission, parent, general, official
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
    status = db.Column(db.String(20), default='checked_in')
    checkout_notes = db.Column(db.Text)
    rating = db.Column(db.Integer)
    
    # ID Card (guest badge) - Foreign Key
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
        """Get the ID card object if assigned"""
        if self.card_id:
            return IDCard.query.get(self.card_id)
        return None
    
    @property
    def is_overdue(self):
        """Check if visitor is overdue"""
        if self.status != 'checked_in' or not self.expected_duration:
            return False
        expected_checkout = self.checkin_time + timedelta(minutes=self.expected_duration)
        return get_indian_time() > expected_checkout
    
    @property
    def duration_display(self):
        """Get duration display string"""
        end_time = self.actual_checkout or get_indian_time()
        duration = end_time - self.checkin_time
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    
    @property
    def has_vehicle(self):
        """Check if visitor has vehicle information"""
        return bool(self.vehicle_number or self.vehicle_type or self.accompanied_count)
    
    @property
    def has_student_info(self):
        """Check if visitor has student/parent information"""
        return bool(self.student_name or self.parent_name or self.student_roll)
    
    @property
    def visit_type_display(self):
        """Get formatted visit type for display"""
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
    hours, remainder = divmod(duration.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return {
        'hours': int(hours),
        'minutes': int(minutes),
        'seconds': int(seconds),
        'total_minutes': int(duration.total_seconds() / 60)
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
        user_agent=request.user_agent.string
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
            print("Initializing ID cards CAS001-CAS100...")
            cards = []
            for i in range(1, 101):
                card = IDCard(
                    card_number=f'CAS{i:03d}',
                    status='available'
                )
                cards.append(card)
            
            # Bulk insert for better performance
            db.session.bulk_save_objects(cards)
            db.session.commit()
            print(f"[OK] Created 100 ID cards (CAS001-CAS100)")
        else:
            print(f"[OK] ID cards already exist ({existing} cards)")
    except Exception as e:
        print(f"[WARNING] Could not initialize ID cards: {e}")
        db.session.rollback()

def get_available_id_card():
    """Get the first available ID card (lowest number)"""
    return IDCard.query.filter_by(status='available').order_by(IDCard.card_number).first()

def get_card_by_number(card_number):
    """Get ID card by its number"""
    return IDCard.query.filter_by(card_number=card_number).first()

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
            return card
        except Exception as e:
            db.session.rollback()
            print(f"Error issuing card: {e}")
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
                return card
        except Exception as e:
            db.session.rollback()
            print(f"Error returning card: {e}")
    return None

def get_current_visitor_for_card(card_id):
    """Get the current visitor who has this card issued"""
    return Visitor.query.filter_by(
        card_id=card_id,
        status='checked_in'
    ).first()

# PostgreSQL-specific function to check and add columns if needed
def upgrade_database_postgresql():
    """Add new columns if they don't exist - PostgreSQL version"""
    with app.app_context():
        try:
            # Get existing columns
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('visitor')]
            
            # Columns to add with their PostgreSQL ALTER statements
            columns_to_add = {
                'vehicle_number': "ALTER TABLE visitor ADD COLUMN IF NOT EXISTS vehicle_number VARCHAR(50)",
                'vehicle_type': "ALTER TABLE visitor ADD COLUMN IF NOT EXISTS vehicle_type VARCHAR(50)",
                'accompanied_count': "ALTER TABLE visitor ADD COLUMN IF NOT EXISTS accompanied_count INTEGER DEFAULT 0",
                'student_name': "ALTER TABLE visitor ADD COLUMN IF NOT EXISTS student_name VARCHAR(100)",
                'parent_name': "ALTER TABLE visitor ADD COLUMN IF NOT EXISTS parent_name VARCHAR(100)",
                'student_roll': "ALTER TABLE visitor ADD COLUMN IF NOT EXISTS student_roll VARCHAR(50)",
                'visit_type': "ALTER TABLE visitor ADD COLUMN IF NOT EXISTS visit_type VARCHAR(50) DEFAULT 'general'"
            }
            
            for col_name, alter_stmt in columns_to_add.items():
                if col_name not in columns:
                    try:
                        db.session.execute(text(alter_stmt))
                        db.session.commit()
                        print(f"[OK] Added {col_name} column")
                    except Exception as e:
                        print(f"[WARNING] Could not add {col_name}: {e}")
                        db.session.rollback()
            
            # Remove email column if exists (no longer collected)
            if 'email' in columns:
                try:
                    # PostgreSQL syntax for dropping column
                    db.session.execute(text('ALTER TABLE visitor DROP COLUMN IF EXISTS email'))
                    db.session.commit()
                    print('[OK] Dropped email column (no longer collected)')
                except Exception as e:
                    print(f'[WARNING] Could not drop email column: {e}')
                    db.session.rollback()
                    
        except Exception as e:
            print(f"[WARNING] Database upgrade check failed: {e}")

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
            next_page = request.args.get('next')
            
            # Redirect based on user role
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
    """ID Cards page - redirects based on role and preserves query parameters"""
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
    """Admin Dashboard - Monitoring and Analytics only (No check-in/out)"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_dashboard'))
    
    now = get_indian_time()
    today_start = datetime(now.year, now.month, now.day)
    
    # Statistics
    total_visitors_today = Visitor.query.filter(
        Visitor.checkin_time >= today_start
    ).count()
    
    active_visitors = Visitor.query.filter_by(status='checked_in').count()
    total_visitors = Visitor.query.count()
    
    # ID Card Statistics
    available_cards = IDCard.query.filter_by(status='available').count()
    issued_cards = IDCard.query.filter_by(status='issued').count()
    lost_cards = IDCard.query.filter_by(status='lost').count()
    damaged_cards = IDCard.query.filter_by(status='damaged').count()
    
    # Recent visitors (last 10) - for monitoring only
    recent_visitors = Visitor.query.order_by(Visitor.checkin_time.desc()).limit(10).all()
    
    # Add card info to recent visitors
    for visitor in recent_visitors:
        if visitor.card_id:
            visitor.card_info = IDCard.query.get(visitor.card_id)
    
    # Department-wise distribution
    dept_stats = db.session.query(
        Visitor.department,
        db.func.count(Visitor.id).label('count')
    ).filter(Visitor.checkin_time >= today_start).group_by(Visitor.department).all()
    
    # Get overdue visitors count
    overdue_count = 0
    for visitor in Visitor.query.filter_by(status='checked_in').all():
        if visitor.expected_duration:
            expected = visitor.checkin_time + timedelta(minutes=visitor.expected_duration)
            if get_indian_time() > expected:
                overdue_count += 1
    
    # Card usage analytics
    card_usage = {
        'total': 100,
        'available': available_cards,
        'issued': issued_cards,
        'utilization': round((issued_cards / 100) * 100, 1) if issued_cards else 0
    }
    
    return render_template('admin_dashboard.html',
                         now=now,
                         total_visitors_today=total_visitors_today,
                         visitors_checked_in=active_visitors,
                         total_visitors=total_visitors,
                         available_cards=available_cards,
                         issued_cards=issued_cards,
                         lost_cards=lost_cards,
                         damaged_cards=damaged_cards,
                         recent_visitors=recent_visitors,
                         dept_stats=dept_stats,
                         overdue_count=overdue_count,
                         card_usage=card_usage,
                         departments=app.config['DEPARTMENTS'])

@app.route('/admin/visitors')
@login_required
def admin_visitors():
    """Admin Visitor Management - Full access with edit/delete"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_visitors'))
    
    status_filter = request.args.get('status', 'all')
    date_filter = request.args.get('date', '')
    department_filter = request.args.get('department', 'all')
    search_query = request.args.get('search', '')
    has_card_filter = request.args.get('has_card', 'all')
    visit_type_filter = request.args.get('visit_type', 'all')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    query = Visitor.query
    
    # Apply filters
    if status_filter == 'checked_in':
        query = query.filter_by(status='checked_in')
    elif status_filter == 'checked_out':
        query = query.filter_by(status='checked_out')
    elif status_filter == 'overdue':
        query = query.filter_by(status='checked_in')
    
    if has_card_filter == 'yes':
        query = query.filter(Visitor.card_id.isnot(None))
    elif has_card_filter == 'no':
        query = query.filter(Visitor.card_id.is_(None))
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(db.func.date(Visitor.checkin_time) == filter_date)
        except ValueError:
            pass
    
    # Date range filter
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Visitor.checkin_time >= start)
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Visitor.checkin_time < end)
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
    
    # execute query and get list
    visitors_list = query.order_by(Visitor.checkin_time.desc()).all()
    
    # Apply overdue filter after query if needed
    if status_filter == 'overdue':
        visitors_list = [v for v in visitors_list if is_overdue(v.checkin_time, v.expected_duration)]
    
    # Calculate additional data for each visitor
    for visitor in visitors_list:
        if visitor.status == 'checked_in':
            visitor.current_duration = calculate_duration(visitor.checkin_time)
            visitor.is_overdue_flag = is_overdue(visitor.checkin_time, visitor.expected_duration)
        elif visitor.actual_checkout:
            visitor.total_duration = calculate_duration(visitor.checkin_time, visitor.actual_checkout)
        if visitor.card_id:
            visitor.card_info = IDCard.query.get(visitor.card_id)
    
    # Calculate statistics
    active_visitors = len([v for v in visitors_list if v.status == 'checked_in'])
    overdue_count = len([v for v in visitors_list if v.status == 'checked_in' and is_overdue(v.checkin_time, v.expected_duration)])
    
    # Pagination
    total_visitors = len(visitors_list)
    total_pages = (total_visitors + per_page - 1) // per_page
    start_index = (page - 1) * per_page
    end_index = min(start_index + per_page, total_visitors)
    visitors_page = visitors_list[start_index:end_index]
    
    return render_template('admin_visitors.html',
                         visitors=visitors_page,
                         total_visitors=total_visitors,
                         active_visitors=active_visitors,
                         overdue_count=overdue_count,
                         checked_out_today=Visitor.query.filter(Visitor.actual_checkout >= datetime.now().replace(hour=0, minute=0, second=0)).count(),
                         page=page,
                         total_pages=total_pages,
                         start_index=start_index + 1,
                         end_index=end_index,
                         status_filter=status_filter,
                         date_filter=date_filter,
                         department_filter=department_filter,
                         has_card_filter=has_card_filter,
                         search_query=search_query,
                         visit_type_filter=visit_type_filter,
                         start_date=start_date,
                         end_date=end_date,
                         departments=app.config['DEPARTMENTS'])

@app.route('/admin/visitor/<visitor_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_visitor(visitor_id):
    """Admin Edit Visitor Details - UPDATE operation"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_visitors'))
    
    visitor = Visitor.query.filter_by(visitor_id=visitor_id).first()
    
    if not visitor:
        flash('Visitor not found', 'error')
        return redirect(url_for('admin_visitors'))
    
    if request.method == 'POST':
        try:
            # Store old values for audit
            old_values = {
                'full_name': visitor.full_name,
                'phone': visitor.phone,
                'id_type': visitor.id_type,
                'id_number': visitor.id_number,
                'company': visitor.company,
                'person_to_meet': visitor.person_to_meet,
                'department': visitor.department,
                'purpose': visitor.purpose,
                'expected_duration': visitor.expected_duration,
                'vehicle_number': visitor.vehicle_number,
                'vehicle_type': visitor.vehicle_type,
                'accompanied_count': visitor.accompanied_count,
                'student_name': visitor.student_name,
                'parent_name': visitor.parent_name,
                'student_roll': visitor.student_roll
            }
            
            # Update visitor details from form
            visitor.full_name = request.form.get('full_name', visitor.full_name)
            visitor.phone = request.form.get('phone', visitor.phone)
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
            
            # Update visit type
            vt = request.form.get('visit_type', '').strip().lower()
            if vt:
                visitor.visit_type = vt
            else:
                # if no explicit type provided, infer from purpose
                p = visitor.purpose.lower()
                if 'admission' in p:
                    visitor.visit_type = 'admission'
                elif 'parent' in p:
                    visitor.visit_type = 'parent'
                elif 'official' in p:
                    visitor.visit_type = 'official'
                else:
                    visitor.visit_type = 'general'
            
            # Update expected duration if provided
            expected_duration = request.form.get('expected_duration')
            if expected_duration and expected_duration.isdigit():
                visitor.expected_duration = int(expected_duration)
                visitor.expected_checkout = visitor.checkin_time + timedelta(minutes=int(expected_duration))
            
            # Vehicle and accompanying info
            visitor.vehicle_number = request.form.get('vehicle_number', visitor.vehicle_number)
            visitor.vehicle_type = request.form.get('vehicle_type', visitor.vehicle_type)
            accompanied = request.form.get('accompanied_count')
            if accompanied and accompanied.isdigit():
                visitor.accompanied_count = int(accompanied)
            
            # Student/parent information
            visitor.student_name = request.form.get('student_name', visitor.student_name)
            visitor.parent_name = request.form.get('parent_name', visitor.parent_name)
            visitor.student_roll = request.form.get('student_roll', visitor.student_roll)
            
            visitor.visit_notes = request.form.get('visit_notes', visitor.visit_notes)
            
            # Handle photo upload
            if 'id_photo' in request.files:
                file = request.files['id_photo']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(f"{visitor.visitor_id}_{file.filename}")
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    visitor.id_photo = filename
            
            db.session.commit()
            
            # Log audit
            log_audit('visitor_updated', 'Visitor', visitor.id, str(old_values), f'Admin updated details for {visitor.visitor_id}')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Visitor updated successfully'})
            
            flash(f'Visitor details updated successfully!', 'success')
            return redirect(url_for('visitor_details', visitor_id=visitor.visitor_id))
            
        except Exception as e:
            db.session.rollback()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': str(e)})
            
            flash(f'Error updating visitor details: {str(e)}', 'error')
            print(f"Update error: {e}")
    
    # GET request - show edit form
    card = None
    if visitor.card_id:
        card = IDCard.query.get(visitor.card_id)
    
    return render_template('admin_edit_visitor.html',
                         visitor=visitor,
                         card=card,
                         departments=app.config['DEPARTMENTS'],
                         purposes=app.config['VISIT_PURPOSES'],
                         id_types=app.config['ID_TYPES'],
                         vehicle_types=app.config['VEHICLE_TYPES'])

@app.route('/admin/idcards')
@login_required
def admin_idcards():
    """Admin ID Card Management - Full control"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_idcards'))
    
    # Statistics
    available_count = IDCard.query.filter_by(status='available').count()
    issued_count = IDCard.query.filter_by(status='issued').count()
    lost_count = IDCard.query.filter_by(status='lost').count()
    damaged_count = IDCard.query.filter_by(status='damaged').count()
    total_count = IDCard.query.count()
    
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Build query
    query = IDCard.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if search_query:
        query = query.filter(IDCard.card_number.ilike(f'%{search_query}%'))
    
    # Pagination
    total_cards = query.count()
    total_pages = (total_cards + per_page - 1) // per_page
    cards = query.order_by(IDCard.card_number).offset((page-1)*per_page).limit(per_page).all()
    
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
                         available_count=available_count,
                         issued_count=issued_count,
                         lost_count=lost_count,
                         damaged_count=damaged_count,
                         total_count=total_count,
                         status_filter=status_filter,
                         search_query=search_query,
                         page=page,
                         total_pages=total_pages)

@app.route('/admin/reports')
@login_required
def admin_reports():
    """Enhanced Reports page - Admin only with comprehensive analytics"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_dashboard'))
    
    # Get filter parameters
    report_type = request.args.get('type', 'daily')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    department = request.args.get('department', '')
    visit_type = request.args.get('visit_type', '')
    status = request.args.get('status', 'all')
    vehicle_status = request.args.get('vehicle_status', 'all')
    student_info = request.args.get('student_info', 'all')
    card_status = request.args.get('card_status', 'all')
    purpose_filter = request.args.get('purpose', '')
    staff_filter = request.args.get('staff', '')
    min_duration = request.args.get('min_duration', '', type=int)
    max_duration = request.args.get('max_duration', '', type=int)
    rating_filter = request.args.get('rating', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = Visitor.query
    
    # Apply date filters
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Visitor.checkin_time >= start)
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Visitor.checkin_time < end)
        except ValueError:
            pass
    
    # Apply other filters
    if department:
        query = query.filter_by(department=department)
    if visit_type:
        query = query.filter_by(visit_type=visit_type)
    if status != 'all':
        query = query.filter_by(status=status)
    if purpose_filter:
        query = query.filter_by(purpose=purpose_filter)
    if staff_filter:
        query = query.filter(Visitor.person_to_meet.ilike(f'%{staff_filter}%'))
    
    # Vehicle status filter
    if vehicle_status == 'with_vehicle':
        query = query.filter(Visitor.vehicle_number.isnot(None))
    elif vehicle_status == 'without_vehicle':
        query = query.filter(Visitor.vehicle_number.is_(None))
    elif vehicle_status == 'two_wheeler':
        query = query.filter_by(vehicle_type='Two Wheeler')
    elif vehicle_status == 'four_wheeler':
        query = query.filter_by(vehicle_type='Four Wheeler')
    
    # Student info filter
    if student_info == 'with_student':
        query = query.filter(Visitor.student_name.isnot(None))
    elif student_info == 'with_parent':
        query = query.filter(Visitor.parent_name.isnot(None))
    elif student_info == 'admission':
        query = query.filter_by(visit_type='admission')
    
    # Card status filter
    if card_status == 'with':
        query = query.filter(Visitor.card_id.isnot(None))
    elif card_status == 'without':
        query = query.filter(Visitor.card_id.is_(None))
    
    # Rating filter
    if rating_filter:
        try:
            rating_val = int(rating_filter)
            query = query.filter_by(rating=rating_val)
        except ValueError:
            pass
    
    # Default to today if no dates specified
    if not start_date and not end_date:
        if report_type == 'daily':
            today = get_indian_time().date()
            query = query.filter(db.func.date(Visitor.checkin_time) == today)
            title = f"Daily Report - {today.strftime('%d/%m/%Y')}"
        elif report_type == 'weekly':
            week_ago = get_indian_time() - timedelta(days=7)
            query = query.filter(Visitor.checkin_time >= week_ago)
            title = "Weekly Report (Last 7 Days)"
        elif report_type == 'monthly':
            month_ago = get_indian_time() - timedelta(days=30)
            query = query.filter(Visitor.checkin_time >= month_ago)
            title = "Monthly Report (Last 30 Days)"
        elif report_type == 'quarterly':
            quarter_ago = get_indian_time() - timedelta(days=90)
            query = query.filter(Visitor.checkin_time >= quarter_ago)
            title = "Quarterly Report (Last 90 Days)"
        elif report_type == 'yearly':
            year_ago = get_indian_time() - timedelta(days=365)
            query = query.filter(Visitor.checkin_time >= year_ago)
            title = "Yearly Report (Last 365 Days)"
        else:
            title = "Complete Report (All Time)"
    else:
        date_range = []
        if start_date:
            date_range.append(f"from {start_date}")
        if end_date:
            date_range.append(f"to {end_date}")
        title = f"Report {' '.join(date_range)}"
    
    # Get all visitors (for stats and list)
    visitors = query.order_by(Visitor.checkin_time.desc()).all()
    
    # Apply duration filter after fetching (since we need calculated duration)
    if min_duration or max_duration:
        filtered_visitors = []
        for v in visitors:
            if v.actual_checkout:
                duration = (v.actual_checkout - v.checkin_time).total_seconds() / 60
                if min_duration and duration < min_duration:
                    continue
                if max_duration and duration > max_duration:
                    continue
                filtered_visitors.append(v)
            elif v.status == 'checked_in' and min_duration:
                # For active visitors, use current duration
                duration = (get_indian_time() - v.checkin_time).total_seconds() / 60
                if duration >= min_duration:
                    filtered_visitors.append(v)
            elif not min_duration and not max_duration:
                filtered_visitors.append(v)
        visitors = filtered_visitors
    
    # ==================== COMPREHENSIVE STATISTICS ====================
    
    # Basic statistics
    total_visitors = len(visitors)
    checked_in_count = len([v for v in visitors if v.status == 'checked_in'])
    checked_out_count = len([v for v in visitors if v.status == 'checked_out'])
    cards_issued_count = len([v for v in visitors if v.card_id])
    
    # Department statistics
    dept_stats = {}
    dept_details = {}
    for visitor in visitors:
        dept = visitor.department
        if dept not in dept_stats:
            dept_stats[dept] = 0
            dept_details[dept] = {
                'total': 0,
                'checked_in': 0,
                'checked_out': 0,
                'with_vehicle': 0,
                'with_card': 0,
                'admission': 0,
                'parent': 0,
                'avg_duration': 0,
                'durations': []
            }
        dept_stats[dept] += 1
        dept_details[dept]['total'] += 1
        
        if visitor.status == 'checked_in':
            dept_details[dept]['checked_in'] += 1
        else:
            dept_details[dept]['checked_out'] += 1
            
        if visitor.vehicle_number:
            dept_details[dept]['with_vehicle'] += 1
        if visitor.card_id:
            dept_details[dept]['with_card'] += 1
        if visitor.visit_type == 'admission':
            dept_details[dept]['admission'] += 1
        if visitor.visit_type == 'parent':
            dept_details[dept]['parent'] += 1
            
        if visitor.actual_checkout:
            duration = (visitor.actual_checkout - visitor.checkin_time).total_seconds() / 60
            dept_details[dept]['durations'].append(duration)
    
    # Calculate average durations per department
    for dept in dept_details:
        if dept_details[dept]['durations']:
            dept_details[dept]['avg_duration'] = round(
                sum(dept_details[dept]['durations']) / len(dept_details[dept]['durations']), 1
            )
    
    # Purpose statistics
    purpose_stats = {}
    for visitor in visitors:
        purpose = visitor.purpose
        purpose_stats[purpose] = purpose_stats.get(purpose, 0) + 1
    
    # ==================== VEHICLE STATISTICS ====================
    vehicle_stats = {
        'total': 0,
        'two_wheeler': 0,
        'four_wheeler': 0,
        'auto': 0,
        'van': 0,
        'bus': 0,
        'truck': 0,
        'other': 0,
        'accompanied_total': 0,
        'accompanied_avg': 0,
        'vehicle_percentage': 0,
        'by_type': {}
    }
    
    vehicle_types_count = {}
    for v in visitors:
        if v.vehicle_number or v.vehicle_type:
            vehicle_stats['total'] += 1
            vt = v.vehicle_type or 'Not Specified'
            vehicle_types_count[vt] = vehicle_types_count.get(vt, 0) + 1
            
            if 'two' in vt.lower():
                vehicle_stats['two_wheeler'] += 1
            elif 'four' in vt.lower():
                vehicle_stats['four_wheeler'] += 1
            elif 'auto' in vt.lower():
                vehicle_stats['auto'] += 1
            elif 'van' in vt.lower():
                vehicle_stats['van'] += 1
            elif 'bus' in vt.lower():
                vehicle_stats['bus'] += 1
            elif 'truck' in vt.lower():
                vehicle_stats['truck'] += 1
            elif vt != 'Not Specified':
                vehicle_stats['other'] += 1
        
        if v.accompanied_count:
            vehicle_stats['accompanied_total'] += v.accompanied_count
    
    vehicle_stats['by_type'] = vehicle_types_count
    if vehicle_stats['total'] > 0:
        vehicle_stats['accompanied_avg'] = round(
            vehicle_stats['accompanied_total'] / vehicle_stats['total'], 1
        )
    if total_visitors > 0:
        vehicle_stats['vehicle_percentage'] = round(
            (vehicle_stats['total'] / total_visitors) * 100, 1
        )
    
    # ==================== STUDENT STATISTICS ====================
    student_stats = {
        'admission_visits': 0,
        'with_student': 0,
        'with_parent': 0,
        'with_roll': 0,
        'unique_students': set(),
        'unique_parents': set(),
        'student_name_percentage': 0,
        'parent_name_percentage': 0,
        'roll_percentage': 0,
        'top_students': [],
        'by_department': {}
    }
    
    student_visits = {}
    for v in visitors:
        if v.visit_type == 'admission':
            student_stats['admission_visits'] += 1
            
        if v.student_name:
            student_stats['with_student'] += 1
            student_stats['unique_students'].add(v.student_name.strip().lower())
            
            # Track student visit frequency
            key = v.student_name.strip()
            if key not in student_visits:
                student_visits[key] = {'count': 0, 'department': v.department}
            student_visits[key]['count'] += 1
            
        if v.parent_name:
            student_stats['with_parent'] += 1
            student_stats['unique_parents'].add(v.parent_name.strip().lower())
            
        if v.student_roll:
            student_stats['with_roll'] += 1
            
        # Department-wise student visits
        if v.student_name or v.visit_type == 'admission':
            dept = v.department
            if dept not in student_stats['by_department']:
                student_stats['by_department'][dept] = 0
            student_stats['by_department'][dept] += 1
    
    # Calculate percentages
    if total_visitors > 0:
        student_stats['student_name_percentage'] = round(
            (student_stats['with_student'] / total_visitors) * 100, 1
        )
        student_stats['parent_name_percentage'] = round(
            (student_stats['with_parent'] / total_visitors) * 100, 1
        )
        student_stats['roll_percentage'] = round(
            (student_stats['with_roll'] / total_visitors) * 100, 1
        )
    
    # Convert sets to counts
    student_stats['unique_students_count'] = len(student_stats['unique_students'])
    student_stats['unique_parents_count'] = len(student_stats['unique_parents'])
    student_stats['unique_students'] = list(student_stats['unique_students'])[:10]  # Top 10 for display
    
    # Get top 5 most visited students
    student_stats['top_students'] = sorted(
        student_visits.items(), 
        key=lambda x: x[1]['count'], 
        reverse=True
    )[:5]
    
    # ==================== PARENT STATISTICS ====================
    parent_stats = {
        'parent_meetings': 0,
        'with_parent': 0,
        'unique_parents': set(),
        'parent_info_percentage': 0,
        'by_department': {}
    }
    
    parent_visits = {}
    for v in visitors:
        if v.visit_type == 'parent':
            parent_stats['parent_meetings'] += 1
            
        if v.parent_name:
            parent_stats['with_parent'] += 1
            parent_stats['unique_parents'].add(v.parent_name.strip().lower())
            
            # Track parent visit frequency
            key = v.parent_name.strip()
            if key not in parent_visits:
                parent_visits[key] = {'count': 0, 'department': v.department, 'student': v.student_name}
            parent_visits[key]['count'] += 1
            
        # Department-wise parent meetings
        if v.parent_name or v.visit_type == 'parent':
            dept = v.department
            if dept not in parent_stats['by_department']:
                parent_stats['by_department'][dept] = 0
            parent_stats['by_department'][dept] += 1
    
    if total_visitors > 0:
        parent_stats['parent_info_percentage'] = round(
            (parent_stats['with_parent'] / total_visitors) * 100, 1
        )
    
    parent_stats['unique_parents_count'] = len(parent_stats['unique_parents'])
    parent_stats['unique_parents'] = list(parent_stats['unique_parents'])[:10]
    
    # Get top 5 most active parents
    parent_stats['top_parents'] = sorted(
        parent_visits.items(),
        key=lambda x: x[1]['count'],
        reverse=True
    )[:5]
    
    # ==================== STAFF STATISTICS ====================
    staff_stats = {
        'by_person': {},
        'top_visited': [],
        'unique_staff': set()
    }
    
    for v in visitors:
        staff = v.person_to_meet
        if staff:
            staff_stats['unique_staff'].add(staff)
            if staff not in staff_stats['by_person']:
                staff_stats['by_person'][staff] = {
                    'count': 0,
                    'department': v.department,
                    'visitors': []
                }
            staff_stats['by_person'][staff]['count'] += 1
            staff_stats['by_person'][staff]['visitors'].append(v.full_name)
    
    staff_stats['unique_staff_count'] = len(staff_stats['unique_staff'])
    staff_stats['top_visited'] = sorted(
        staff_stats['by_person'].items(),
        key=lambda x: x[1]['count'],
        reverse=True
    )[:10]
    
    # ==================== SATISFACTION STATISTICS ====================
    ratings = [v.rating for v in visitors if v.rating is not None]
    rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    for r in ratings:
        if r in rating_distribution:
            rating_distribution[r] += 1
    
    satisfaction = {
        'avg_rating': round(sum(ratings) / len(ratings), 2) if ratings else 0,
        'total_ratings': len(ratings),
        'rating_percentage': round((len(ratings) / total_visitors * 100), 1) if total_visitors > 0 else 0,
        'distribution': rating_distribution,
        'five_star': rating_distribution[5],
        'four_star': rating_distribution[4],
        'three_star': rating_distribution[3],
        'two_star': rating_distribution[2],
        'one_star': rating_distribution[1]
    }
    
    # ==================== TIME-BASED STATISTICS ====================
    time_stats = {
        'hourly': {},
        'weekday': {},
        'monthly': {},
        'peak_hours': []
    }
    
    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    for v in visitors:
        # Hourly distribution
        hour = v.checkin_time.hour
        time_stats['hourly'][hour] = time_stats['hourly'].get(hour, 0) + 1
        
        # Weekday distribution
        weekday = weekdays[v.checkin_time.weekday()]
        time_stats['weekday'][weekday] = time_stats['weekday'].get(weekday, 0) + 1
        
        # Monthly distribution
        month = v.checkin_time.strftime('%B %Y')
        time_stats['monthly'][month] = time_stats['monthly'].get(month, 0) + 1
    
    # Get peak hours (top 5)
    time_stats['peak_hours'] = sorted(
        time_stats['hourly'].items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    # ==================== DURATION STATISTICS ====================
    durations = []
    for v in visitors:
        if v.actual_checkout:
            duration = (v.actual_checkout - v.checkin_time).total_seconds() / 60
            durations.append(duration)
        elif v.status == 'checked_in':
            duration = (get_indian_time() - v.checkin_time).total_seconds() / 60
            durations.append(duration)
    
    duration_stats = {
        'avg': round(sum(durations) / len(durations), 1) if durations else 0,
        'min': round(min(durations), 1) if durations else 0,
        'max': round(max(durations), 1) if durations else 0,
        'total_durations': len(durations),
        'by_range': {
            '<15 min': len([d for d in durations if d < 15]),
            '15-30 min': len([d for d in durations if 15 <= d < 30]),
            '30-60 min': len([d for d in durations if 30 <= d < 60]),
            '1-2 hours': len([d for d in durations if 60 <= d < 120]),
            '2-4 hours': len([d for d in durations if 120 <= d < 240]),
            '>4 hours': len([d for d in durations if d >= 240])
        }
    }
    
    # ==================== CARD STATISTICS ====================
    card_stats = {
        'issued': cards_issued_count,
        'issued_percentage': round((cards_issued_count / total_visitors * 100), 1) if total_visitors > 0 else 0,
        'returned': len([v for v in visitors if v.card_returned_date]),
        'active_cards': IDCard.query.filter_by(status='issued').count(),
        'available_cards': IDCard.query.filter_by(status='available').count(),
        'lost_cards': IDCard.query.filter_by(status='lost').count(),
        'damaged_cards': IDCard.query.filter_by(status='damaged').count(),
        'total_cards': IDCard.query.count()
    }
    
    # ==================== TREND DATA FOR CHARTS ====================
    # Last 30 days trend
    trend_labels = []
    trend_values = []
    for i in range(30, 0, -1):
        date = get_indian_time().date() - timedelta(days=i)
        count = len([v for v in visitors if v.checkin_time.date() == date])
        trend_labels.append(date.strftime('%d %b'))
        trend_values.append(count)
    
    trend_data = {
        'labels': trend_labels,
        'values': trend_values
    }
    
    # Department data for charts
    dept_chart_data = {
        'labels': list(dept_stats.keys()),
        'values': list(dept_stats.values())
    }
    
    # Visit types for chart
    visit_type_counts = {
        'admission': len([v for v in visitors if v.visit_type == 'admission']),
        'parent': len([v for v in visitors if v.visit_type == 'parent']),
        'official': len([v for v in visitors if v.visit_type == 'official']),
        'general': len([v for v in visitors if v.visit_type == 'general'])
    }
    
    # Purpose data for chart (top 10)
    purpose_chart_data = {
        'labels': list(purpose_stats.keys())[:10],
        'values': list(purpose_stats.values())[:10]
    }
    
    # Hourly data for chart
    hourly_chart_data = {
        'labels': [f"{h}:00" for h in range(8, 20)],
        'values': [time_stats['hourly'].get(h, 0) for h in range(8, 20)]
    }
    
    # ==================== ACTIVE FILTERS COUNT ====================
    active_filters = 0
    if start_date: active_filters += 1
    if end_date: active_filters += 1
    if department: active_filters += 1
    if visit_type: active_filters += 1
    if status != 'all': active_filters += 1
    if vehicle_status != 'all': active_filters += 1
    if student_info != 'all': active_filters += 1
    if card_status != 'all': active_filters += 1
    if purpose_filter: active_filters += 1
    if staff_filter: active_filters += 1
    if min_duration: active_filters += 1
    if max_duration: active_filters += 1
    if rating_filter: active_filters += 1
    
    # ==================== PAGINATION ====================
    total_pages = (total_visitors + per_page - 1) // per_page
    start_index = (page - 1) * per_page
    end_index = min(start_index + per_page, total_visitors)
    visitors_page = visitors[start_index:end_index]
    
    # Add card info to paginated visitors
    for visitor in visitors_page:
        if visitor.card_id:
            visitor.card_info = IDCard.query.get(visitor.card_id)
    
    # ==================== RENDER TEMPLATE ====================
    # Provide a default stats dictionary for template compatibility
    stats = {
        'total': total_visitors,
        'checked_in': checked_in_count,
        'checked_out': checked_out_count,
        'cards_issued': cards_issued_count
    }
    return render_template('admin_reports.html',
                         min=min,
                         stats=stats,
                         # Basic data
                         visitors=visitors_page,
                         total_visitors=total_visitors,
                         page=page,
                         total_pages=total_pages,
                         per_page=per_page,
                         start_index=start_index + 1,
                         end_index=end_index,
                         
                         # Filter parameters
                         title=title,
                         start_date=start_date,
                         end_date=end_date,
                         department_filter=department,
                         visit_type_filter=visit_type,
                         status_filter=status,
                         vehicle_status_filter=vehicle_status,
                         student_info_filter=student_info,
                         card_filter=card_status,
                         purpose_filter=purpose_filter,
                         staff_filter=staff_filter,
                         min_duration=min_duration,
                         max_duration=max_duration,
                         rating_filter=rating_filter,
                         active_filters=active_filters,
                         
                         # Basic statistics
                         total_visitors_count=total_visitors,
                         checked_in_count=checked_in_count,
                         checked_out_count=checked_out_count,
                         cards_issued_count=cards_issued_count,
                         
                         # Detailed statistics
                         dept_stats=dept_stats,
                         dept_details=dept_details,
                         purpose_stats=purpose_stats,
                         vehicle_stats=vehicle_stats,
                         student_stats=student_stats,
                         parent_stats=parent_stats,
                         staff_stats=staff_stats,
                         satisfaction=satisfaction,
                         time_stats=time_stats,
                         duration_stats=duration_stats,
                         card_stats=card_stats,
                         
                         # Chart data
                         trend_data=trend_data,
                         dept_chart_data=dept_chart_data,
                         visit_type_counts=visit_type_counts,
                         purpose_chart_data=purpose_chart_data,
                         hourly_chart_data=hourly_chart_data,
                         
                         # Configuration
                         departments=app.config['DEPARTMENTS'],
                         purposes=app.config['VISIT_PURPOSES'],
                         vehicle_types=app.config['VEHICLE_TYPES'])

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    """Settings page - Admin only. GET shows form, POST saves to database."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_dashboard'))

    if request.method == 'POST':
        # update all generic settings
        for key, value in request.form.items():
            if key.startswith('setting_'):
                real_key = key[len('setting_'):]
                setting = Settings.query.filter_by(key=real_key).first()
                if setting:
                    setting.value = value
                else:
                    # create new setting if it doesn't exist
                    setting = Settings(key=real_key, value=value)
                    db.session.add(setting)
        # update dynamic lists (comma separated) and persist to settings table
        if 'departments_list' in request.form:
            deps = [d.strip() for d in request.form['departments_list'].split(',') if d.strip()]
            app.config['DEPARTMENTS'] = deps
            s = Settings.query.filter_by(key='departments').first()
            if not s:
                s = Settings(key='departments', value=','.join(deps))
                db.session.add(s)
            else:
                s.value = ','.join(deps)
        if 'purposes_list' in request.form:
            purps = [p.strip() for p in request.form['purposes_list'].split(',') if p.strip()]
            app.config['VISIT_PURPOSES'] = purps
            s = Settings.query.filter_by(key='purposes').first()
            if not s:
                s = Settings(key='purposes', value=','.join(purps))
                db.session.add(s)
            else:
                s.value = ','.join(purps)
        if 'id_types_list' in request.form:
            ids = [i.strip() for i in request.form['id_types_list'].split(',') if i.strip()]
            app.config['ID_TYPES'] = ids
            s = Settings.query.filter_by(key='id_types').first()
            if not s:
                s = Settings(key='id_types', value=','.join(ids))
                db.session.add(s)
            else:
                s.value = ','.join(ids)
        db.session.commit()
        flash('Settings updated successfully.', 'success')
        return redirect(url_for('admin_settings'))

    all_settings = Settings.query.all()
    settings_dict = {setting.key: setting.value for setting in all_settings}

    # override dynamic lists if stored in settings table
    if 'departments' in settings_dict:
        app.config['DEPARTMENTS'] = [d.strip() for d in settings_dict['departments'].split(',') if d.strip()]
    if 'purposes' in settings_dict:
        app.config['VISIT_PURPOSES'] = [p.strip() for p in settings_dict['purposes'].split(',') if p.strip()]
    if 'id_types' in settings_dict:
        app.config['ID_TYPES'] = [i.strip() for i in settings_dict['id_types'].split(',') if i.strip()]
    
    return render_template('admin_settings.html',
                         settings=settings_dict,
                         departments=app.config['DEPARTMENTS'],
                         purposes=app.config['VISIT_PURPOSES'],
                         id_types=app.config['ID_TYPES'])

# Redirect old /settings endpoint to admin_settings
@app.route('/settings')
@login_required
def settings():
    """Redirect settings endpoint to admin_settings"""
    if current_user.is_admin:
        return redirect(url_for('admin_settings'))
    else:
        flash('Access denied. Settings are only available to admins.', 'warning')
        return redirect(url_for('security_dashboard'))

# ===================== DELETE ROUTES =====================
@app.route('/security/visitors/<visitor_id>/delete', methods=['POST'])
@login_required
def delete_visitor(visitor_id):
    """DELETE operation - Single visitor deletion"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    try:
        visitor = Visitor.query.filter_by(visitor_id=visitor_id).first()
        
        if not visitor:
            return jsonify({'success': False, 'message': 'Visitor not found'}), 404
        
        # Store visitor info for audit
        visitor_name = visitor.full_name
        visitor_id_num = visitor.visitor_id
        
        # Release card if assigned
        if visitor.card_id:
            card = IDCard.query.get(visitor.card_id)
            if card:
                card.status = 'available'
                card.returned_date = get_indian_time()
        
        db.session.delete(visitor)
        db.session.commit()
        
        # Log audit
        log_audit('visitor_deleted', 'Visitor', visitor.id, None, f'Deleted visitor {visitor_id_num} - {visitor_name}')
        
        return jsonify({'success': True, 'message': f'Visitor {visitor_name} deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/security/visitors/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_visitors():
    """BULK DELETE operation - Multiple visitors deletion"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    try:
        data = request.get_json()
        visitor_ids = data.get('visitor_ids', [])
        
        if not visitor_ids:
            return jsonify({'success': False, 'message': 'No visitors selected'}), 400
        
        deleted_count = 0
        deleted_names = []
        
        for visitor_id in visitor_ids:
            visitor = Visitor.query.filter_by(visitor_id=visitor_id).first()
            if visitor:
                # Release card if assigned
                if visitor.card_id:
                    card = IDCard.query.get(visitor.card_id)
                    if card:
                        card.status = 'available'
                        card.returned_date = get_indian_time()
                
                deleted_names.append(visitor.full_name)
                db.session.delete(visitor)
                deleted_count += 1
        
        db.session.commit()
        
        # Log audit
        log_audit('bulk_delete', 'Visitor', None, None, f'Deleted {deleted_count} visitors: {", ".join(deleted_names)}')
        
        return jsonify({'success': True, 'message': f'Successfully deleted {deleted_count} visitors'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# ===================== NOTIFICATIONS ROUTES =====================
@app.route('/notifications')
@login_required
def notifications():
    """Notifications page - Shows alerts and overdue visitors"""
    try:
        # Get all active (checked-in) visitors
        active_visitors = Visitor.query.filter_by(status='checked_in').all()
        
        # Find overdue visitors
        overdue_visitors = []
        now = get_indian_time()
        
        for visitor in active_visitors:
            if is_overdue(visitor.checkin_time, visitor.expected_duration):
                time_exceeded = calculate_duration(visitor.checkin_time)['total_minutes'] - visitor.expected_duration
                overdue_visitors.append({
                    'visitor': visitor,
                    'duration_exceeded': f"{time_exceeded} min"
                })
        
        # Get ID card statistics
        available_cards = IDCard.query.filter_by(status='available').count()
        damaged_cards = IDCard.query.filter_by(status='damaged').count()
        lost_cards = IDCard.query.filter_by(status='lost').count()
        issued_cards = IDCard.query.filter_by(status='issued').count()
        
        # Check if cards are low (less than 5 available)
        low_cards = available_cards < 5
        
        dashboard_alerts = {
            'overdue_visitors': len(overdue_visitors),
            'available_cards': available_cards,
            'damaged_cards': damaged_cards,
            'lost_cards': lost_cards,
            'issued_cards': issued_cards,
            'low_cards': low_cards
        }
        
        active_visitors_count = len(active_visitors)
        
        return render_template('notifications.html',
                             alerts=overdue_visitors,
                             dashboard_alerts=dashboard_alerts,
                             active_visitors_count=active_visitors_count)
    except Exception as e:
        print(f"Error loading notifications: {e}")
        flash('Error loading notifications. Please try again.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/api/notifications')
@login_required
def api_notifications():
    """API endpoint for getting notifications as JSON"""
    try:
        # Get all active (checked-in) visitors
        active_visitors = Visitor.query.filter_by(status='checked_in').all()
        
        # Find overdue visitors
        overdue_visitors = []
        now = get_indian_time()
        
        for visitor in active_visitors:
            if is_overdue(visitor.checkin_time, visitor.expected_duration):
                time_exceeded = calculate_duration(visitor.checkin_time)['total_minutes'] - visitor.expected_duration
                overdue_visitors.append({
                    'visitor_id': visitor.visitor_id,
                    'name': visitor.full_name,
                    'department': visitor.department,
                    'checkin_time': visitor.checkin_time.isoformat(),
                    'duration_exceeded_minutes': time_exceeded,
                    'url': url_for('visitor_details', visitor_id=visitor.visitor_id)
                })
        
        # Get ID card statistics
        available_cards = IDCard.query.filter_by(status='available').count()
        damaged_cards = IDCard.query.filter_by(status='damaged').count()
        lost_cards = IDCard.query.filter_by(status='lost').count()
        
        return jsonify({
            'success': True,
            'notifications': overdue_visitors,
            'summary': {
                'overdue_count': len(overdue_visitors),
                'active_visitors': Visitor.query.filter_by(status='checked_in').count(),
                'available_cards': available_cards,
                'damaged_cards': damaged_cards,
                'lost_cards': lost_cards
            }
        })
    except Exception as e:
        print(f"Error in API notifications: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'notifications': []
        }), 500

# ===================== SECURITY ROUTES =====================
@app.route('/security/dashboard')
@login_required
def security_dashboard():
    """Security Dashboard - For security staff with check-in/out"""
    now = get_indian_time()
    today_start = datetime(now.year, now.month, now.day)
    
    # Security-specific statistics
    active_visitors = Visitor.query.filter_by(status='checked_in').count()
    total_visitors_today = Visitor.query.filter(Visitor.checkin_time >= today_start).count()
    available_cards = IDCard.query.filter_by(status='available').count()
    
    # Checked out today
    checked_out_today = Visitor.query.filter(
        Visitor.actual_checkout >= today_start
    ).count()
    
    # Active visitors list (for quick view)
    active_visitors_list = Visitor.query.filter_by(status='checked_in').order_by(Visitor.checkin_time.desc()).limit(10).all()
    
    for visitor in active_visitors_list:
        visitor.is_overdue_flag = is_overdue(visitor.checkin_time, visitor.expected_duration)
        if visitor.card_id:
            visitor.card_info = IDCard.query.get(visitor.card_id)
    
    # Recent check-outs
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
    """Security Visitor Management - View only"""
    status_filter = request.args.get('status', 'all')
    date_filter = request.args.get('date', '')
    search_query = request.args.get('search', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    query = Visitor.query
    
    # Apply filters (simplified for security)
    if status_filter == 'checked_in':
        query = query.filter_by(status='checked_in')
    elif status_filter == 'checked_out':
        query = query.filter_by(status='checked_out')
    elif status_filter == 'overdue':
        query = query.filter_by(status='checked_in')
    
    # Date range filter
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Visitor.checkin_time >= start)
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Visitor.checkin_time < end)
        except ValueError:
            pass
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter(db.func.date(Visitor.checkin_time) == filter_date)
        except ValueError:
            pass
    
    if search_query:
        search = f"%{search_query}%"
        query = query.filter(
            db.or_(
                Visitor.visitor_id.ilike(search),
                Visitor.full_name.ilike(search),
                Visitor.phone.ilike(search),
                Visitor.vehicle_number.ilike(search),
                Visitor.student_name.ilike(search),
                Visitor.parent_name.ilike(search)
            )
        )
    
    visitors_list = query.order_by(Visitor.checkin_time.desc()).all()
    
    # Apply overdue filter after query if needed
    if status_filter == 'overdue':
        visitors_list = [v for v in visitors_list if is_overdue(v.checkin_time, v.expected_duration)]
    
    # Calculate additional data for each visitor
    for visitor in visitors_list:
        if visitor.status == 'checked_in':
            visitor.current_duration = calculate_duration(visitor.checkin_time)
            visitor.is_overdue_flag = is_overdue(visitor.checkin_time, visitor.expected_duration)
        elif visitor.actual_checkout:
            visitor.total_duration = calculate_duration(visitor.checkin_time, visitor.actual_checkout)
        if visitor.card_id:
            visitor.card_info = IDCard.query.get(visitor.card_id)
    
    # Calculate statistics
    active_visitors = len([v for v in visitors_list if v.status == 'checked_in'])
    overdue_count = len([v for v in visitors_list if v.status == 'checked_in' and is_overdue(v.checkin_time, v.expected_duration)])
    
    # Pagination
    total_visitors = len(visitors_list)
    total_pages = (total_visitors + per_page - 1) // per_page
    start_index = (page - 1) * per_page
    end_index = min(start_index + per_page, total_visitors)
    visitors_page = visitors_list[start_index:end_index]
    
    return render_template('security_visitors.html',
                         visitors=visitors_page,
                         total_visitors=total_visitors,
                         active_visitors=active_visitors,
                         overdue_count=overdue_count,
                         checked_out_today=Visitor.query.filter(Visitor.actual_checkout >= datetime.now().replace(hour=0, minute=0, second=0)).count(),
                         page=page,
                         total_pages=total_pages,
                         start_index=start_index + 1,
                         end_index=end_index,
                         status_filter=status_filter,
                         date_filter=date_filter,
                         search_query=search_query,
                         start_date=start_date,
                         end_date=end_date)

@app.route('/security/idcards')
@login_required
def security_idcards():
    """Security ID Card Management - View only"""
    # Statistics
    available_count = IDCard.query.filter_by(status='available').count()
    issued_count = IDCard.query.filter_by(status='issued').count()
    lost_count = IDCard.query.filter_by(status='lost').count()
    damaged_count = IDCard.query.filter_by(status='damaged').count()
    total_count = IDCard.query.count()
    
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Build query
    query = IDCard.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if search_query:
        query = query.filter(IDCard.card_number.ilike(f'%{search_query}%'))
    
    # Pagination
    total_cards = query.count()
    total_pages = (total_cards + per_page - 1) // per_page
    cards = query.order_by(IDCard.card_number).offset((page-1)*per_page).limit(per_page).all()
    
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
    
    return render_template('security_idcards.html',
                         cards=card_data,
                         available_count=available_count,
                         issued_count=issued_count,
                         lost_count=lost_count,
                         damaged_count=damaged_count,
                         total_count=total_count,
                         status_filter=status_filter,
                         search_query=search_query,
                         page=page,
                         total_pages=total_pages)

# ===================== SHARED ROUTES =====================
@app.route('/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    """Visitor check-in page - For security staff - CREATE operation"""
    if request.method == 'POST':
        try:
            # Generate visitor ID
            visitor_id = generate_visitor_id()
            
            # Parse expected duration
            expected_duration = request.form.get('expected_duration')
            if expected_duration and expected_duration.isdigit():
                expected_duration = int(expected_duration)
                expected_checkout = get_indian_time() + timedelta(minutes=expected_duration)
            else:
                expected_duration = None
                expected_checkout = None
            
            # Determine visit type from hidden form field (set by JS)
            visit_type = request.form.get('visit_type', '').strip().lower()
            if not visit_type:
                # fallback to inference for backward compatibility
                p = request.form.get('purpose', '').lower()
                if 'admission' in p:
                    visit_type = 'admission'
                elif 'parent' in p:
                    visit_type = 'parent'
                elif 'official' in p:
                    visit_type = 'official'
                else:
                    visit_type = 'general'

            # Capture purpose text from form
            purpose_value = request.form.get('purpose', '').strip()

            # Create visitor record with ALL fields
            visitor = Visitor(
                visitor_id=visitor_id,
                full_name=request.form.get('full_name', '').strip(),
                phone=request.form.get('phone', '').strip(),
                address=request.form.get('address', '').strip(),
                city=request.form.get('city', '').strip(),
                state=request.form.get('state', '').strip(),
                pincode=request.form.get('pincode', '').strip(),
                id_type=request.form.get('id_type', ''),
                id_number=request.form.get('id_number', '').strip(),
                company=request.form.get('company', '').strip(),
                person_to_meet=request.form.get('person_to_meet', '').strip(),
                department=request.form.get('department', 'Administration'),
                purpose=purpose_value,
                visit_type=visit_type,
                expected_duration=expected_duration,
                expected_checkout=expected_checkout,
                visit_notes=request.form.get('visit_notes', '').strip(),
                # Student/parent info
                student_name=request.form.get('student_name', '').strip(),
                parent_name=request.form.get('parent_name', '').strip(),
                student_roll=request.form.get('student_roll', '').strip(),
                # Vehicle information
                vehicle_number=request.form.get('vehicle_number', '').strip(),
                vehicle_type=request.form.get('vehicle_type', '').strip(),
                accompanied_count=int(request.form.get('accompanied_count') or 0),
                checkin_by=current_user.id,
                status='checked_in'
            )
            
            # Handle photo upload if any
            if 'id_photo' in request.files:
                file = request.files['id_photo']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(f"{visitor_id}_{file.filename}")
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    visitor.id_photo = filename
            
            db.session.add(visitor)
            db.session.commit()
            
            # Issue ID card to visitor (if available)
            card = issue_id_card(visitor)
            
            # Generate QR code
            if card:
                qr_data = f"Visitor ID: {visitor_id}\nName: {visitor.full_name}\nCard: {card.card_number}\nCheck-in: {visitor.checkin_time.strftime('%Y-%m-%d %H:%M')}"
                card_message = f" | Card Issued: {card.card_number}"
            else:
                qr_data = f"Visitor ID: {visitor_id}\nName: {visitor.full_name}\nCheck-in: {visitor.checkin_time.strftime('%Y-%m-%d %H:%M')}"
                card_message = " | No ID card available"
            
            qr_code = create_qr_code(qr_data)
            
            # Log audit
            log_audit('visitor_checkin', 'Visitor', visitor.id, None, visitor_id)
            if card:
                log_audit('card_issued', 'IDCard', card.id, 'available', f'issued to {visitor_id}')
            
            flash(f'Visitor {visitor.full_name} checked in successfully! Visitor ID: {visitor_id}{card_message}', 'success')
            
            # Render success page with QR code
            return render_template('checkin_success.html',
                                 visitor=visitor,
                                 qr_code=qr_code,
                                 visitor_id=visitor_id,
                                 card=card,
                                 departments=app.config['DEPARTMENTS'])
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error checking in visitor: {str(e)}', 'error')
            print(f"Check-in error: {e}")
            import traceback
            traceback.print_exc()
    
    # GET request - show form
    available_cards_count = IDCard.query.filter_by(status='available').count()
    
    return render_template('checkin.html',
                         departments=app.config['DEPARTMENTS'],
                         purposes=app.config['VISIT_PURPOSES'],
                         id_types=app.config['ID_TYPES'],
                         vehicle_types=app.config['VEHICLE_TYPES'],
                         available_cards=available_cards_count,
                         now=get_indian_time_display())

@app.route('/checkout', methods=['GET', 'POST'])
@app.route('/checkout_page', methods=['GET', 'POST'], endpoint='checkout_page')
@login_required
def checkout():
    """Visitor check-out page - For security staff"""
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
                
                # Calculate actual duration
                duration = calculate_duration(visitor.checkin_time, visitor.actual_checkout)
                
                # Return ID card if issued
                card = None
                card_info = ""
                if visitor.card_id:
                    card = return_id_card(visitor)
                    if card:
                        card_info = f" | Card {card.card_number} returned"
                
                db.session.commit()
                
                # Log audit
                log_audit('visitor_checkout', 'Visitor', visitor.id, 'checked_in', 'checked_out')
                if card:
                    log_audit('card_returned', 'IDCard', card.id, 'issued', 'available')
                
                flash(f'Visitor {visitor.full_name} checked out successfully!{card_info}', 'success')
                
                # Generate receipt data
                receipt_data = {
                    'visitor': visitor,
                    'duration': duration,
                    'checked_out_by': current_user,
                    'card': card
                }
                
                return render_template('checkout_success.html', **receipt_data)
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error checking out visitor: {str(e)}', 'error')
                print(f"Checkout error: {e}")
        else:
            flash('Visitor not found or already checked out', 'error')
    
    # GET request - show checkout interface
    active_visitors = Visitor.query.filter_by(status='checked_in').order_by(Visitor.checkin_time.desc()).all()
    
    # Calculate durations and status for server-side display
    for visitor in active_visitors:
        visitor.duration = calculate_duration(visitor.checkin_time)
        visitor.is_overdue_flag = is_overdue(visitor.checkin_time, visitor.expected_duration)
        visitor.status_text = get_status_text(visitor.checkin_time, visitor.expected_duration)
        if visitor.card_id:
            visitor.card_info = IDCard.query.get(visitor.card_id)

    # Build a JSON-serializable representation for client-side JS
    active_visitors_json = []
    for v in active_visitors:
        card_number = None
        if v.card_id:
            c = IDCard.query.get(v.card_id)
            if c:
                card_number = c.card_number

        active_visitors_json.append({
            'id': v.id,
            'visitor_id': v.visitor_id,
            'full_name': v.full_name,
            'phone': v.phone,
            'checkin_time': v.checkin_time.isoformat() if v.checkin_time else None,
            'is_overdue': getattr(v, 'is_overdue_flag', is_overdue(v.checkin_time, v.expected_duration)),
            'card_id': v.card_id,
            'card_number': card_number,
            'department': v.department,
            'person_to_meet': v.person_to_meet,
            'purpose': v.purpose,
            'expected_duration': v.expected_duration,
            'status_text': getattr(v, 'status_text', get_status_text(v.checkin_time, v.expected_duration)),
            'vehicle_number': v.vehicle_number,
            'vehicle_type': v.vehicle_type,
            'accompanied_count': v.accompanied_count,
            'student_name': v.student_name,
            'parent_name': v.parent_name,
            'student_roll': v.student_roll
        })  

    return render_template('checkout.html',
                         active_visitors=active_visitors,
                         active_visitors_json=active_visitors_json,
                         departments=app.config['DEPARTMENTS'],
                         vehicle_types=app.config['VEHICLE_TYPES'])

@app.route('/checkout_success')
@login_required
def checkout_success():
    """Checkout success page - GET endpoint used after API/QR checkouts"""
    visitor_id = request.args.get('visitor_id', '')
    if not visitor_id:
        flash('Missing visitor ID for checkout success page.', 'error')
        return redirect(url_for('checkout_page'))
    visitor = Visitor.query.filter_by(visitor_id=visitor_id).first()
    if not visitor:
        flash('Visitor not found.', 'error')
        return redirect(url_for('checkout_page'))

    duration = None
    if visitor.checkin_time and visitor.actual_checkout:
        duration = calculate_duration(visitor.checkin_time, visitor.actual_checkout)
    card = None
    if visitor.card_id:
        card = IDCard.query.get(visitor.card_id)

    receipt_data = {
        'visitor': visitor,
        'duration': duration,
        'checked_out_by': current_user,
        'card': card
    }
    return render_template('checkout_success.html', **receipt_data)

@app.route('/visitor/<visitor_id>')
@login_required
def visitor_details(visitor_id):
    """Visitor details page - READ operation - Shared by both roles - Shows ALL fields"""
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
    
    if visitor.card_id:
        visitor.card_info = IDCard.query.get(visitor.card_id)
    
    visitor.is_overdue_flag = is_overdue_flag
    
    # Get card info
    card = IDCard.query.get(visitor.card_id) if visitor.card_id else None
    
    # Get checkin/checkout user details
    checkin_user = None
    if visitor.checkin_by:
        checkin_user = User.query.get(visitor.checkin_by)
    
    checkout_user = None
    if visitor.checkout_by:
        checkout_user = User.query.get(visitor.checkout_by)
    
    # Generate QR code if visitor is active
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
    """View ID card details and history - Shared by both roles"""
    card = IDCard.query.filter_by(card_number=card_number).first_or_404()
    
    # Get current visitor if issued
    current_visitor = None
    if card.status == 'issued':
        current_visitor = Visitor.query.filter_by(
            card_id=card.id,
            status='checked_in'
        ).first()
    
    # Get history of this card (all visitors who used it)
    history = Visitor.query.filter_by(card_id=card.id).order_by(
        Visitor.card_issued_date.desc()
    ).limit(20).all()
    
    return render_template('idcard_details.html',
                         card=card,
                         current_visitor=current_visitor,
                         history=history)

# ===================== API ROUTES =====================
@app.route('/api/card/<int:card_id>/status', methods=['POST'])
@login_required
def update_card_status(card_id):
    """Update ID card status (mark as lost, damaged, available) - Admin only"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    card = IDCard.query.get(card_id)
    if not card:
        return jsonify({'success': False, 'message': 'Card not found'}), 404
    
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['available', 'lost', 'damaged']:
            return jsonify({'success': False, 'message': 'Invalid status'}), 400
        
        # If card is issued, cannot change status directly
        if card.status == 'issued' and new_status != 'issued':
            return jsonify({
                'success': False, 
                'message': f'Card is currently issued. Please check out the visitor first.'
            }), 400
        
        old_status = card.status
        card.status = new_status
        
        if new_status == 'available':
            card.returned_date = get_indian_time()
        
        db.session.commit()
        
        log_audit('card_status_update', 'IDCard', card.id, old_status, new_status)
        
        return jsonify({
            'success': True,
            'message': f'Card {card.card_number} status updated to {new_status}',
            'card': {
                'id': card.id,
                'number': card.card_number,
                'status': card.status
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/cards/status')
@login_required
def api_cards_status():
    """API endpoint to get card status counts"""
    try:
        available = IDCard.query.filter_by(status='available').count()
        issued = IDCard.query.filter_by(status='issued').count()
        lost = IDCard.query.filter_by(status='lost').count()
        damaged = IDCard.query.filter_by(status='damaged').count()
        total = IDCard.query.count()
        
        return jsonify({
            'available': available,
            'issued': issued,
            'lost': lost,
            'damaged': damaged,
            'total': total,
            'returned_today': IDCard.query.filter(
                IDCard.returned_date >= get_indian_time().replace(hour=0, minute=0, second=0)
            ).count()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cards/available')
@login_required
def api_available_cards():
    """API endpoint to get available cards"""
    cards = IDCard.query.filter_by(status='available').order_by(IDCard.card_number).all()
    
    return jsonify({
        'success': True,
        'count': len(cards),
        'cards': [{'id': c.id, 'number': c.card_number} for c in cards]
    })

@app.route('/api/cards/issued')
@login_required
def api_issued_cards():
    """API endpoint to get issued cards with visitor info"""
    cards = IDCard.query.filter_by(status='issued').all()
    
    card_data = []
    for card in cards:
        visitor = Visitor.query.filter_by(card_id=card.id, status='checked_in').first()
        card_data.append({
            'id': card.id,
            'number': card.card_number,
            'visitor': {
                'id': visitor.id if visitor else None,
                'visitor_id': visitor.visitor_id if visitor else None,
                'name': visitor.full_name if visitor else None,
                'checkin_time': visitor.checkin_time.isoformat() if visitor else None
            } if visitor else None
        })
    
    return jsonify({
        'success': True,
        'count': len(cards),
        'cards': card_data
    })

@app.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    """API endpoint for dashboard statistics"""
    try:
        now = get_indian_time()
        today_start = datetime(now.year, now.month, now.day)
        
        # Calculate today's visitors
        today_count = Visitor.query.filter(Visitor.checkin_time >= today_start).count()
        
        # Calculate active visitors
        active_count = Visitor.query.filter_by(status='checked_in').count()
        
        # Calculate total visitors
        total_count = Visitor.query.count()
        
        # Calculate available cards
        available_cards = IDCard.query.filter_by(status='available').count()
        
        # Calculate checked out today
        checked_out_today = Visitor.query.filter(
            Visitor.actual_checkout >= today_start
        ).count()
        
        # Calculate cards returned today
        cards_returned_today = IDCard.query.filter(
            IDCard.returned_date >= today_start
        ).count()
        
        # Calculate average visit time using PostgreSQL interval handling
        avg_visit_query = db.session.query(
            db.func.avg(
                db.func.extract('epoch', Visitor.actual_checkout - Visitor.checkin_time) / 60
            )
        ).filter(
            Visitor.actual_checkout.isnot(None),
            Visitor.checkin_time >= today_start
        ).scalar()
        
        if avg_visit_query:
            minutes = int(avg_visit_query)
            hours = minutes // 60
            mins = minutes % 60
            avg_visit = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        else:
            avg_visit = "0m"
        
        # Calculate overdue count
        overdue_count = 0
        active_visitors = Visitor.query.filter_by(status='checked_in').all()
        for visitor in active_visitors:
            if visitor.expected_duration and is_overdue(visitor.checkin_time, visitor.expected_duration):
                overdue_count += 1
        
        # Calculate yesterday's count for trend
        yesterday_start = today_start - timedelta(days=1)
        yesterday_count = Visitor.query.filter(
            Visitor.checkin_time >= yesterday_start,
            Visitor.checkin_time < today_start
        ).count()
        
        # Determine trend
        trend_icon = 'up' if today_count > yesterday_count else 'down'
        trend_class = 'trend-up' if today_count > yesterday_count else 'trend-down'
        trend_text = f"{abs(today_count - yesterday_count)} from yesterday"
        
        return jsonify({
            'visitors_today': today_count,
            'active_visitors': active_count,
            'total_visitors': total_count,
            'available_cards': available_cards,
            'checked_out_today': checked_out_today,
            'cards_returned_today': cards_returned_today,
            'avg_visit_time': avg_visit,
            'overdue_count': overdue_count,
            'trends': {
                'visitors': {
                    'icon': trend_icon,
                    'class': trend_class,
                    'text': trend_text
                }
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/visitor/<visitor_id>')
@login_required
def api_visitor_details(visitor_id):
    """API endpoint to get visitor details by ID"""
    try:
        visitor = Visitor.query.filter_by(visitor_id=visitor_id, status='checked_in').first()
        
        if not visitor:
            return jsonify({'error': 'Visitor not found'}), 404
        
        # Get card info if any
        card_info = None
        if visitor.card_id:
            card = IDCard.query.get(visitor.card_id)
            if card:
                card_info = {
                    'id': card.id,
                    'number': card.card_number,
                    'status': card.status
                }
        
        return jsonify({
            'id': visitor.id,
            'visitor_id': visitor.visitor_id,
            'full_name': visitor.full_name,
            'phone': visitor.phone,
            'person_to_meet': visitor.person_to_meet,
            'department': visitor.department,
            'purpose': visitor.purpose,
            'checkin_time': visitor.checkin_time.isoformat(),
            'expected_duration': visitor.expected_duration,
            'card_id': visitor.card_id,
            'card_number': card_info['number'] if card_info else None,
            'card_issued_date': visitor.card_issued_date.isoformat() if visitor.card_issued_date else None,
            'vehicle_number': visitor.vehicle_number,
            'vehicle_type': visitor.vehicle_type,
            'accompanied_count': visitor.accompanied_count,
            'student_name': visitor.student_name,
            'parent_name': visitor.parent_name,
            'student_roll': visitor.student_roll
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/visitors/overdue/count')
@login_required
def api_overdue_count():
    """API endpoint to get overdue visitors count"""
    try:
        overdue_count = 0
        active_visitors = Visitor.query.filter_by(status='checked_in').all()
        for visitor in active_visitors:
            if visitor.expected_duration and is_overdue(visitor.checkin_time, visitor.expected_duration):
                overdue_count += 1
        
        return jsonify({'count': overdue_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chart-data')
@login_required
def api_chart_data():
    """API endpoint for chart data"""
    try:
        chart_type = request.args.get('type', 'department')
        now = get_indian_time()
        today_start = datetime(now.year, now.month, now.day)
        
        if chart_type == 'department':
            # Department distribution
            dept_stats = db.session.query(
                Visitor.department,
                db.func.count(Visitor.id).label('count')
            ).filter(Visitor.checkin_time >= today_start).group_by(Visitor.department).all()
            
            labels = [stat[0] for stat in dept_stats]
            values = [stat[1] for stat in dept_stats]
        else:
            # Purpose distribution
            purpose_stats = db.session.query(
                Visitor.purpose,
                db.func.count(Visitor.id).label('count')
            ).filter(Visitor.checkin_time >= today_start).group_by(Visitor.purpose).all()
            
            labels = [stat[0] for stat in purpose_stats]
            values = [stat[1] for stat in purpose_stats]
        
        return jsonify({
            'labels': labels,
            'values': values
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/checkout/<visitor_id>', methods=['POST'])
@login_required
def checkout_visitor(visitor_id):
    """API endpoint for checking out a visitor"""
    visitor = Visitor.query.filter_by(visitor_id=visitor_id, status='checked_in').first()
    
    if not visitor:
        return jsonify({'success': False, 'message': 'Visitor not found or already checked out'})
    
    try:
        # Try to parse JSON data with multiple fallback methods
        data = {}
        try:
            if request.is_json:
                data = request.get_json() or {}
            else:
                # Try manual JSON parsing
                import json
                json_str = request.data.decode('utf-8')
                if json_str:
                    data = json.loads(json_str)
                else:
                    data = request.form.to_dict()
        except Exception as parse_error:
            # Fallback to form data
            data = request.form.to_dict()
        
        visitor.actual_checkout = get_indian_time()
        visitor.checkout_by = current_user.id
        visitor.status = 'checked_out'
        visitor.checkout_notes = data.get('checkout_notes', '')
        
        rating = data.get('rating')
        if rating:
            visitor.rating = int(rating)
        
        # Return ID card if issued
        card_returned = False
        if visitor.card_id:
            card = return_id_card(visitor)
            card_returned = bool(card)
        
        db.session.commit()
        
        # Log audit
        log_audit('visitor_checkout_api', 'Visitor', visitor.id, 'checked_in', 'checked_out')
        
        return jsonify({
            'success': True,
            'message': f'Visitor {visitor.full_name} checked out successfully',
            'visitor_id': visitor.visitor_id,
            'checkout_time': visitor.actual_checkout.isoformat(),
            'card_returned': card_returned
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/visitors/active')
@login_required
def api_active_visitors():
    """API endpoint for active visitors"""
    active_visitors = Visitor.query.filter_by(status='checked_in').order_by(Visitor.checkin_time.desc()).all()
    
    visitors_data = []
    for visitor in active_visitors:
        duration = calculate_duration(visitor.checkin_time)
        card_number = None
        if visitor.card_id:
            card = IDCard.query.get(visitor.card_id)
            card_number = card.card_number if card else None
        
        visitors_data.append({
            'id': visitor.id,
            'visitor_id': visitor.visitor_id,
            'full_name': visitor.full_name,
            'phone': visitor.phone,
            'person_to_meet': visitor.person_to_meet,
            'department': visitor.department,
            'purpose': visitor.purpose,
            'checkin_time': visitor.checkin_time.isoformat(),
            'duration': f"{duration['hours']}h {duration['minutes']}m",
            'is_overdue': is_overdue(visitor.checkin_time, visitor.expected_duration),
            'status_text': get_status_text(visitor.checkin_time, visitor.expected_duration),
            'card_number': card_number,
            'vehicle_number': visitor.vehicle_number,
            'vehicle_type': visitor.vehicle_type,
            'accompanied_count': visitor.accompanied_count,
            'student_name': visitor.student_name,
            'parent_name': visitor.parent_name,
            'student_roll': visitor.student_roll
        })
    
    return jsonify(visitors_data)

@app.route('/api/visitors/today')
@login_required
def api_visitors_today():
    """API endpoint for today's visitors"""
    today_start = get_indian_time().replace(hour=0, minute=0, second=0, microsecond=0)
    today_visitors = Visitor.query.filter(Visitor.checkin_time >= today_start).all()
    
    stats = {
        'total': len(today_visitors),
        'checked_in': len([v for v in today_visitors if v.status == 'checked_in']),
        'checked_out': len([v for v in today_visitors if v.status == 'checked_out']),
        'cards_issued': len([v for v in today_visitors if v.card_id]),
        'by_department': {}
    }
    
    # Count by department
    for dept in app.config['DEPARTMENTS']:
        count = len([v for v in today_visitors if v.department == dept])
        if count > 0:
            stats['by_department'][dept] = count
    
    return jsonify(stats)

@app.route('/api/reports')
@login_required
def api_reports():
    """API endpoint for reports data - Admin only"""
    if not current_user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403
    
    report_type = request.args.get('type', 'daily')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    query = Visitor.query
    
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Visitor.checkin_time >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Visitor.checkin_time < end)
        except ValueError:
            pass
    
    if not start_date and not end_date:
        if report_type == 'daily':
            today = get_indian_time().date()
            query = query.filter(db.func.date(Visitor.checkin_time) == today)
        elif report_type == 'weekly':
            week_ago = get_indian_time() - timedelta(days=7)
            query = query.filter(Visitor.checkin_time >= week_ago)
        elif report_type == 'monthly':
            month_ago = get_indian_time() - timedelta(days=30)
            query = query.filter(Visitor.checkin_time >= month_ago)
    
    visitors = query.order_by(Visitor.checkin_time.desc()).all()
    
    # Calculate statistics
    total_visitors = len(visitors)
    checked_in_count = len([v for v in visitors if v.status == 'checked_in'])
    checked_out_count = len([v for v in visitors if v.status == 'checked_out'])
    cards_issued_count = len([v for v in visitors if v.card_id])
    
    # Department stats
    dept_stats = {}
    for visitor in visitors:
        if visitor.department not in dept_stats:
            dept_stats[visitor.department] = 0
        dept_stats[visitor.department] += 1
    
    # Purpose stats
    purpose_stats = {}
    for visitor in visitors:
        if visitor.purpose not in purpose_stats:
            purpose_stats[visitor.purpose] = 0
        purpose_stats[visitor.purpose] += 1
    
    # Calculate average duration using PostgreSQL interval handling
    total_duration = 0
    duration_count = 0
    for visitor in visitors:
        if visitor.actual_checkout:
            delta = (visitor.actual_checkout - visitor.checkin_time).total_seconds()
            total_duration += delta
            duration_count += 1
    
    avg_duration = int(total_duration / duration_count / 60) if duration_count > 0 else 0
    
    # Card usage statistics
    card_stats = {
        'issued': cards_issued_count,
        'returned': len([v for v in visitors if v.card_returned_date]),
        'active': IDCard.query.filter_by(status='issued').count()
    }
    
    # Prepare hourly distribution
    hourly_data = {}
    for visitor in visitors:
        hour = visitor.checkin_time.hour
        if hour not in hourly_data:
            hourly_data[hour] = 0
        hourly_data[hour] += 1
    
    # Prepare trend data (last 7 days)
    trend_data = {'labels': [], 'values': []}
    for i in range(7):
        date = get_indian_time().date() - timedelta(days=6-i)
        count = len([v for v in visitors if v.checkin_time.date() == date])
        trend_data['labels'].append(date.strftime('%a'))
        trend_data['values'].append(count)
    
    # Prepare department data
    dept_data = {
        'labels': list(dept_stats.keys()),
        'values': list(dept_stats.values())
    }
    
    # Prepare time data
    time_data = {'labels': [], 'values': []}
    for hour in range(8, 19):
        time_data['labels'].append(f"{hour}:00")
        time_data['values'].append(hourly_data.get(hour, 0))
    
    # Calculate insights
    busiest_dept = max(dept_stats, key=dept_stats.get) if dept_stats else 'N/A'
    busiest_dept_count = dept_stats.get(busiest_dept, 0) if dept_stats else 0
    
    most_common_purpose = max(purpose_stats, key=purpose_stats.get) if purpose_stats else 'N/A'
    most_common_count = purpose_stats.get(most_common_purpose, 0) if purpose_stats else 0
    
    peak_hour = max(hourly_data, key=hourly_data.get) if hourly_data else 10
    peak_count = hourly_data.get(peak_hour, 0) if hourly_data else 0
    
    stats = {
        'totalVisitors': total_visitors,
        'activeVisitors': checked_in_count,
        'cardsIssued': cards_issued_count,
        'departmentsCount': len(dept_stats),
        'avgDuration': avg_duration
    }
    
    insights = {
        'busiestDept': busiest_dept,
        'busiestDeptStats': f'{busiest_dept_count} visitors',
        'peakHours': f'{peak_hour}:00 - {peak_hour+1}:00',
        'peakHourStats': f'{peak_count} visits',
        'commonVisitType': most_common_purpose,
        'visitTypeStats': f'{most_common_count} visits',
        'avgVisitDuration': f'{avg_duration} minutes'
    }
    
    return jsonify({
        'visitors': len(visitors),
        'stats': stats,
        'cardStats': card_stats,
        'trendData': trend_data,
        'departmentData': dept_data,
        'timeData': time_data,
        'insights': insights
    })

@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    try:
        db.session.execute(text('SELECT 1'))
        
        # Check ID cards count
        cards_count = IDCard.query.count()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': get_indian_time_display().isoformat(),
            'database': 'connected',
            'id_cards': cards_count,
            'version': '2.1.0-postgresql'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# ===================== EXPORT ROUTES (Admin only) =====================
@app.route('/export/csv')
@login_required
def export_csv():
    """Export visitors data as CSV - Admin only - Includes ALL fields"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_dashboard'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    query = Visitor.query
    
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Visitor.checkin_time >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Visitor.checkin_time < end)
        except ValueError:
            pass
    
    visitors = query.order_by(Visitor.checkin_time.desc()).all()
    
    # Create CSV
    output = BytesIO()
    writer = csv.writer(output)
    
    # Write header with ALL fields
    writer.writerow([
        'Visitor ID', 'Full Name', 'Phone', 'Address', 'City', 'State', 'Pincode',
        'ID Type', 'ID Number', 'Company',
        'Student Name', 'Parent Name', 'Student Roll',
        'Vehicle Number', 'Vehicle Type', 'Accompanied Count',
        'Person to Meet', 'Department', 'Purpose', 'Visit Type',
        'Expected Duration', 'Check-in Time', 'Expected Checkout', 'Check-out Time',
        'Status', 'ID Card', 'Card Issued Date', 'Card Returned Date',
        'Check-in By', 'Check-out By', 'Visit Notes', 'Check-out Notes', 'Rating',
        'Created At', 'Updated At'
    ])
    
    # Write data
    for visitor in visitors:
        card_number = ''
        if visitor.card_id:
            card = IDCard.query.get(visitor.card_id)
            card_number = card.card_number if card else ''
        
        checkin_user_name = visitor.checkin_user.full_name if visitor.checkin_user else ''
        checkout_user_name = visitor.checkout_user.full_name if visitor.checkout_user else ''
        
        writer.writerow([
            visitor.visitor_id,
            visitor.full_name,
            visitor.phone,
            visitor.address or '',
            visitor.city or '',
            visitor.state or '',
            visitor.pincode or '',
            visitor.id_type or '',
            visitor.id_number or '',
            visitor.company or '',
            visitor.student_name or '',
            visitor.parent_name or '',
            visitor.student_roll or '',
            visitor.vehicle_number or '',
            visitor.vehicle_type or '',
            visitor.accompanied_count or 0,
            visitor.person_to_meet,
            visitor.department,
            visitor.purpose,
            visitor.visit_type,
            visitor.expected_duration or '',
            visitor.checkin_time.strftime('%Y-%m-%d %H:%M:%S'),
            visitor.expected_checkout.strftime('%Y-%m-%d %H:%M:%S') if visitor.expected_checkout else '',
            visitor.actual_checkout.strftime('%Y-%m-%d %H:%M:%S') if visitor.actual_checkout else '',
            visitor.status,
            card_number,
            visitor.card_issued_date.strftime('%Y-%m-%d %H:%M:%S') if visitor.card_issued_date else '',
            visitor.card_returned_date.strftime('%Y-%m-%d %H:%M:%S') if visitor.card_returned_date else '',
            checkin_user_name,
            checkout_user_name,
            visitor.visit_notes or '',
            visitor.checkout_notes or '',
            visitor.rating or '',
            visitor.created_at.strftime('%Y-%m-%d %H:%M:%S') if visitor.created_at else '',
            visitor.updated_at.strftime('%Y-%m-%d %H:%M:%S') if visitor.updated_at else ''
        ])
    
    output.seek(0)
    
    log_audit('export_csv')
    
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'visitors_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

@app.route('/export/pdf')
@login_required
def export_pdf():
    """Export visitors data as PDF - Admin only"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('security_dashboard'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    query = Visitor.query
    
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Visitor.checkin_time >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Visitor.checkin_time < end)
        except ValueError:
            pass
    
    visitors = query.order_by(Visitor.checkin_time.desc()).limit(100).all()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    styles = getSampleStyleSheet()
    
    title_text = f"KPR College Visitor Report"
    if start_date or end_date:
        title_text += f" ({start_date} to {end_date})"
    
    elements.append(Paragraph(title_text, styles['Title']))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    elements.append(Paragraph(f"Generated by: {current_user.full_name or current_user.username}", styles['Normal']))
    elements.append(Paragraph(" ", styles['Normal']))
    
    # Prepare data for table
    data = [['Visitor ID', 'Name', 'Department', 'Purpose', 'Vehicle', 'ID Card', 'Check-in', 'Check-out', 'Status']]
    
    for visitor in visitors:
        card_number = ''
        if visitor.card_id:
            card = IDCard.query.get(visitor.card_id)
            card_number = card.card_number if card else ''
        
        vehicle_info = visitor.vehicle_number or 'No vehicle'
        
        data.append([
            visitor.visitor_id,
            visitor.full_name[:20] + '...' if len(visitor.full_name) > 20 else visitor.full_name,
            visitor.department,
            visitor.purpose[:15] + '...' if len(visitor.purpose) > 15 else visitor.purpose,
            vehicle_info,
            card_number,
            visitor.checkin_time.strftime('%d/%m %H:%M'),
            visitor.actual_checkout.strftime('%d/%m %H:%M') if visitor.actual_checkout else 'N/A',
            visitor.status.title()
        ])
    
    if len(data) > 1:
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(table)
    else:
        elements.append(Paragraph("No visitor data found for the selected period.", styles['Normal']))
    
    # Add summary
    elements.append(Paragraph(" ", styles['Normal']))
    elements.append(Paragraph(f"Total Visitors: {len(visitors)}", styles['Normal']))
    
    # Add card summary
    cards_issued = len([v for v in visitors if v.card_id])
    elements.append(Paragraph(f"ID Cards Issued: {cards_issued}", styles['Normal']))
    
    # Add vehicle summary
    vehicles_count = len([v for v in visitors if v.vehicle_number])
    elements.append(Paragraph(f"Vehicles Registered: {vehicles_count}", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    log_audit('export_pdf')
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'visitors_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )

# ===================== DEBUG ROUTES =====================
@app.route('/debug/reset-admin')
def debug_reset_admin():
    """Debug route to reset admin password (remove in production)"""
    admin = User.query.filter_by(username='admin').first()
    if admin:
        admin.set_password('admin')
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Admin password reset to admin',
            'username': 'admin'
        })
    return jsonify({'success': False, 'message': 'Admin user not found'})

@app.route('/debug/create-test-users')
def debug_create_test_users():
    """Create test users for debugging"""
    users = [
        {
            'username': 'admin',
            'password': 'admin',
            'email': 'admin@kprcollege.edu',
            'full_name': 'Administrator',
            'department': 'Administration',
            'is_admin': True
        },
        {
            'username': 'security',
            'password': 'security123',
            'email': 'security@kprcollege.edu',
            'full_name': 'Security Officer',
            'department': 'Security',
            'is_admin': False
        },

    ]
    
    results = []
    for user_data in users:
        user = User.query.filter_by(username=user_data['username']).first()
        if user:
            user.set_password(user_data['password'])
            user.is_admin = user_data['is_admin']
            user.email = user_data['email']
            user.full_name = user_data['full_name']
            user.department = user_data['department']
            results.append(f"Updated: {user_data['username']} (is_admin={user_data['is_admin']})")
        else:
            user = User(
                username=user_data['username'],
                email=user_data['email'],
                full_name=user_data['full_name'],
                department=user_data['department'],
                is_admin=user_data['is_admin'],
                is_active=True
            )
            user.set_password(user_data['password'])
            db.session.add(user)
            results.append(f"Created: {user_data['username']}")
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'users': results
    })

@app.route('/debug/reset-id-cards')
@login_required
def debug_reset_id_cards():
    """Debug route to reset ID cards (admin only)"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    try:
        # Delete all cards
        IDCard.query.delete()
        db.session.commit()
        
        # Reinitialize
        cards = []
        for i in range(1, 101):
            card = IDCard(
                card_number=f'CAS{i:03d}',
                status='available'
            )
            cards.append(card)
        
        db.session.bulk_save_objects(cards)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'ID cards reset successfully',
            'count': 100
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/debug/test-postgresql')
@login_required
def debug_test_postgresql():
    """Test PostgreSQL connection and show database info"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Admin access required'}), 403
    
    try:
        # Test connection
        result = db.session.execute(text("SELECT 1")).scalar()
        
        # Get PostgreSQL version
        version = db.session.execute(text("SELECT version()")).scalar()
        
        # Get current database
        db_name = db.session.execute(text("SELECT current_database()")).scalar()
        
        # Get table counts
        user_count = User.query.count()
        id_card_count = IDCard.query.count()
        visitor_count = Visitor.query.count()
        settings_count = Settings.query.count()
        audit_log_count = AuditLog.query.count()
        
        # Get table list
        tables = db.session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).fetchall()
        table_list = [t[0] for t in tables]
        
        return jsonify({
            'success': True,
            'connection': 'successful',
            'postgresql_version': version,
            'database': db_name,
            'tables': table_list,
            'counts': {
                'users': user_count,
                'id_cards': id_card_count,
                'visitors': visitor_count,
                'settings': settings_count,
                'audit_logs': audit_log_count
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ===================== ERROR HANDLERS =====================
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

# ===================== INITIALIZATION =====================
def create_default_settings():
    """Create default settings if they don't exist"""
    default_settings = [
        ('college_name', 'KPR College of Arts Science and Research', 'College name'),
        ('college_address', 'Coimbatore, Tamil Nadu', 'College address'),
        ('college_phone', '+91 422 1234567', 'College phone number'),
        ('college_email', 'info@kprcollege.edu', 'College email'),
        ('visitor_pass_validity', '8', 'Visitor pass validity in hours'),
        ('auto_checkout_hours', '12', 'Auto checkout after hours'),
        ('enable_email_notifications', 'true', 'Enable email notifications'),
        ('enable_sms_notifications', 'false', 'Enable SMS notifications'),
        ('qr_code_size', '200', 'QR code size in pixels'),
        ('default_department', 'Administration', 'Default department'),
        ('max_visitors_per_day', '100', 'Maximum visitors per day'),
        ('enable_camera_capture', 'true', 'Enable camera capture for ID'),
        ('enable_biometric', 'false', 'Enable biometric verification'),
        ('theme_color', '#1a237e', 'Primary theme color'),
        ('backup_frequency', 'daily', 'Backup frequency'),
        ('data_retention_days', '365', 'Data retention in days'),
    ]
    
    for key, value, description in default_settings:
        setting = Settings.query.filter_by(key=key).first()
        if not setting:
            setting = Settings(key=key, value=value, description=description)
            db.session.add(setting)
    
    db.session.commit()

def create_default_admin():
    """Create default admin user if not exists.  Also overwrite password if it looks hashed."""
    username = app.config.get('DEFAULT_ADMIN_USERNAME')
    password = app.config.get('DEFAULT_ADMIN_PASSWORD')

    admin = User.query.filter_by(username=username).first()
    if not admin:
        admin = User(
            username=username,
            email='admin@kprcollege.edu',
            full_name='Administrator',
            department='Administration',
            phone='+91 9876543210',
            is_admin=True,
            is_active=True
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print("[OK] Default admin user created successfully!")
        print(f"   Username: {username}")
        print(f"   Password: {password}")
    else:
        # if existing password contains a hash prefix, overwrite it
        if admin.password_hash and admin.password_hash.startswith('pbkdf2:'):
            admin.set_password(password)
            db.session.commit()
            print("[OK] Admin password upgraded to plain text from config")
        else:
            print("[OK] Admin user already exists")

def create_default_security():
    """Create default security user if not exists.  Also overwrite password if it looks hashed."""
    username = app.config.get('DEFAULT_SECURITY_USERNAME')
    password = app.config.get('DEFAULT_SECURITY_PASSWORD')

    security = User.query.filter_by(username=username).first()
    if not security:
        security = User(
            username=username,
            email='security@kprcollege.edu',
            full_name='Security Officer',
            department='Security',
            phone='+91 9876543211',
            is_admin=False,
            is_active=True
        )
        security.set_password(password)
        db.session.add(security)
        db.session.commit()
        print("[OK] Default security user created successfully!")
        print(f"   Username: {username}")
        print(f"   Password: {password}")
    else:
        # if existing password contains a hash prefix, overwrite it
        if security.password_hash and security.password_hash.startswith('pbkdf2:'):
            security.set_password(password)
            db.session.commit()
            print("[OK] Security password upgraded to plain text from config")
        else:
            print("[OK] Security user already exists")

def init_database():
    """Initialize database with required data"""
    with app.app_context():
        try:
            # Test PostgreSQL connection
            db.session.execute(text('SELECT 1'))
            print("[OK] PostgreSQL connection successful")
            
            # Create all tables (if they don't exist)
            db.create_all()
            print("[OK] Database tables verified/created")
            
            # Check and upgrade database schema for PostgreSQL
            upgrade_database_postgresql()
            
            # Initialize ID cards if needed
            initialize_id_cards()
            
            # Create default admin if not exists
            create_default_admin()
            
            # Create default security if not exists
            create_default_security()
            
            # Create default settings
            create_default_settings()
            print("[OK] Default settings created")
            
        except Exception as e:
            print(f"[ERROR] Database initialization failed: {e}")
            raise

def print_startup_info():
    """Print startup information - must be called within app context"""
    with app.app_context():
        available_cards = IDCard.query.filter_by(status='available').count()
        issued_cards = IDCard.query.filter_by(status='issued').count()
        lost_cards = IDCard.query.filter_by(status='lost').count()
        damaged_cards = IDCard.query.filter_by(status='damaged').count()
        
        # Get PostgreSQL info
        try:
            db_name = db.session.execute(text("SELECT current_database()")).scalar()
            db_version = db.session.execute(text("SELECT version()")).scalar()
        except:
            db_name = "Unknown"
            db_version = "Unknown"
        
        print("\n" + "="*60)
        print("KPR COLLEGE VISITOR MANAGEMENT SYSTEM - POSTGRESQL EDITION")
        print("="*60)
        print(f"PostgreSQL Database: {db_name}")
        print(f"PostgreSQL Version:  {db_version}")
        print(f"Server URL:     http://localhost:5000")
        print(f"Admin Login:    admin / admin")
        print(f"Security Login: security / security123")
        print(f"ID Cards:       {available_cards} available, {issued_cards} issued, {lost_cards} lost, {damaged_cards} damaged")
        print("="*60)
        print("Press Ctrl+C to stop\n")

# ===================== APPLICATION ENTRY POINT =====================
if __name__ == '__main__':
    # Install required packages if not already installed
    required_packages = ['psycopg2-binary', 'python-dotenv', 'qrcode', 'reportlab', 'pytz']
    
    # Initialize database
    init_database()
    
    # Print startup info
    print_startup_info()
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)
