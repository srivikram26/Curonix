# ============================================================
# Authentication Routes
# Handles registration, login, logout for all user roles
# ============================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, date
from app.factory import db
from app.models import User, Doctor, Department, DoctorAvailability
from werkzeug.security import generate_password_hash
import functools

auth_bp = Blueprint('auth', __name__)

ALLOWED_DOCTOR_ID_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
MAX_DOCTOR_ID_UPLOAD_SIZE_MB = 5


def get_doctor_allowed_domains():
    """Return normalized list of allowed email domains for doctor verification."""
    domains = current_app.config.get('DOCTOR_ALLOWED_EMAIL_DOMAINS', ['hospital.com'])
    if isinstance(domains, str):
        domains = [domains]
    return [domain.strip().lower() for domain in domains if str(domain).strip()]


def is_valid_doctor_email(email):
    """Check if email belongs to an allowed doctor domain."""
    if not email or '@' not in email:
        return False

    email = email.strip().lower()
    allowed_domains = get_doctor_allowed_domains()
    return any(email.endswith(f"@{domain}") for domain in allowed_domains)


# ============================================================
# Role-based access decorators
# ============================================================
def role_required(role):
    """Decorator to restrict access to specific user roles."""
    def decorator(f):
        @functools.wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role != role:
                flash('Access denied. Insufficient permissions.', 'danger')
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================
# Page Routes (HTML rendering)
# ============================================================

@auth_bp.route('/login', strict_slashes=False)
def login_page():
    """Render login page."""
    if current_user.is_authenticated:
        return redirect_by_role()
    role = request.args.get('role', 'patient')
    if role not in ['patient', 'doctor', 'admin']:
        role = 'patient'
    return render_template('auth/login.html', role=role)


@auth_bp.route('/select-role', strict_slashes=False)
def select_role_page():
    """Render role selection page."""
    if current_user.is_authenticated:
        return redirect_by_role()
    return render_template('auth/select_role.html')


@auth_bp.route('/verify-doctor', strict_slashes=False)
def verify_doctor_page():
    """Render doctor email domain verification page."""
    if current_user.is_authenticated:
        return redirect_by_role()
    return render_template('auth/verify_doctor.html')


@auth_bp.route('/register', strict_slashes=False)
def register_page():
    """Render registration page with role."""
    if current_user.is_authenticated:
        return redirect_by_role()
    role = request.args.get('role', 'patient')
    if role not in ['patient', 'doctor', 'admin']:
        role = 'patient'

    verified_email = None
    verified_first_name = None
    verified_last_name = None
    if role == 'doctor':
        doctor_verified = session.get('doctor_verified', False)
        verification_method = session.get('doctor_verification_method')
        verified_email = session.get('doctor_verified_email')
        verified_first_name = session.get('doctor_verified_first_name')
        verified_last_name = session.get('doctor_verified_last_name')
        if not doctor_verified or verification_method != 'both':
            flash('Doctor verification is required before registration.', 'warning')
            return redirect(url_for('auth.verify_doctor_page'))

    return render_template(
        'auth/register.html',
        role=role,
        verified_email=verified_email,
        verified_first_name=verified_first_name,
        verified_last_name=verified_last_name
    )


@auth_bp.route('/forgot-password', strict_slashes=False)
def forgot_password_page():
    """Render forgot password page."""
    if current_user.is_authenticated:
        return redirect_by_role()
    role = request.args.get('role', 'patient')
    if role not in ['patient', 'doctor', 'admin']:
        role = 'patient'
    return render_template('auth/forgot_password.html', role=role)


@auth_bp.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    """
    Reset password for a user account.
    
    Expected JSON body:
        - email, new_password
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    email = data.get('email')
    new_password = data.get('new_password')
    
    if not email or not new_password:
        return jsonify({'success': False, 'error': 'Email and new password are required'}), 400
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return jsonify({'success': False, 'error': 'No account found with this email address'}), 404
    
    # Update password
    user.set_password(new_password)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Password reset successful! Please login with your new password.',
        'role': user.role
    })


@auth_bp.route('/api/verify-doctor', methods=['POST'])
def verify_doctor():
    """Verify doctor email domain before allowing doctor registration."""
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'success': False, 'error': 'Email is required'}), 400

    if not is_valid_doctor_email(email):
        allowed_domains = ', '.join(get_doctor_allowed_domains())
        return jsonify({
            'success': False,
            'error': f'Doctor verification failed. Please use an approved hospital email ({allowed_domains}).'
        }), 403

    session['doctor_verified'] = True
    session['doctor_verification_method'] = 'email'
    session['doctor_verified_email'] = email

    return jsonify({
        'success': True,
        'message': 'Doctor verification successful. Continue registration.',
        'redirect': url_for('auth.register_page', role='doctor')
    })


@auth_bp.route('/api/verify-doctor-id-scan', methods=['POST'])
def verify_doctor_id_scan():
    """Verify doctor via hospital ID scan upload before registration."""
    if 'id_scan' not in request.files:
        return jsonify({'success': False, 'error': 'Please upload a hospital ID scan'}), 400

    id_scan = request.files['id_scan']
    if not id_scan or not id_scan.filename:
        return jsonify({'success': False, 'error': 'Please upload a valid ID scan file'}), 400

    filename = id_scan.filename.strip().lower()
    if '.' not in filename:
        return jsonify({'success': False, 'error': 'Invalid file format'}), 400

    extension = filename.rsplit('.', 1)[1]
    if extension not in ALLOWED_DOCTOR_ID_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_DOCTOR_ID_EXTENSIONS))
        return jsonify({'success': False, 'error': f'Unsupported file type. Allowed: {allowed}'}), 400

    max_size_bytes = MAX_DOCTOR_ID_UPLOAD_SIZE_MB * 1024 * 1024
    if request.content_length and request.content_length > max_size_bytes:
        return jsonify({
            'success': False,
            'error': f'File too large. Max size is {MAX_DOCTOR_ID_UPLOAD_SIZE_MB}MB'
        }), 413

    session['doctor_verified'] = True
    session['doctor_verification_method'] = 'id_scan'
    session.pop('doctor_verified_email', None)

    return jsonify({
        'success': True,
        'message': 'Hospital ID scan verified. Continue registration.',
        'redirect': url_for('auth.register_page', role='doctor')
    })


@auth_bp.route('/api/verify-doctor-complete', methods=['POST'])
def verify_doctor_complete():
    """Verify doctor using both approved email domain and hospital ID scan."""
    email = (request.form.get('email') or '').strip().lower()
    first_name = (request.form.get('first_name') or '').strip()
    last_name = (request.form.get('last_name') or '').strip()

    if not first_name or not last_name:
        return jsonify({'success': False, 'error': 'First name and last name are required'}), 400

    if not email:
        return jsonify({'success': False, 'error': 'Email is required'}), 400

    if not is_valid_doctor_email(email):
        allowed_domains = ', '.join(get_doctor_allowed_domains())
        return jsonify({
            'success': False,
            'error': f'Doctor verification failed. Please use an approved hospital email ({allowed_domains}).'
        }), 403

    if 'id_scan' not in request.files:
        return jsonify({'success': False, 'error': 'Please upload a hospital ID scan'}), 400

    id_scan = request.files['id_scan']
    if not id_scan or not id_scan.filename:
        return jsonify({'success': False, 'error': 'Please upload a valid ID scan file'}), 400

    filename = id_scan.filename.strip().lower()
    if '.' not in filename:
        return jsonify({'success': False, 'error': 'Invalid file format'}), 400

    extension = filename.rsplit('.', 1)[1]
    if extension not in ALLOWED_DOCTOR_ID_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_DOCTOR_ID_EXTENSIONS))
        return jsonify({'success': False, 'error': f'Unsupported file type. Allowed: {allowed}'}), 400

    max_size_bytes = MAX_DOCTOR_ID_UPLOAD_SIZE_MB * 1024 * 1024
    if request.content_length and request.content_length > max_size_bytes:
        return jsonify({
            'success': False,
            'error': f'File too large. Max size is {MAX_DOCTOR_ID_UPLOAD_SIZE_MB}MB'
        }), 413

    session['doctor_verified'] = True
    session['doctor_verification_method'] = 'both'
    session['doctor_verified_email'] = email
    session['doctor_verified_first_name'] = first_name
    session['doctor_verified_last_name'] = last_name

    return jsonify({
        'success': True,
        'message': 'Email and hospital ID verification successful. Continue registration.',
        'redirect': url_for('auth.register_page', role='doctor')
    })


# ============================================================
# API Routes (JSON responses)
# ============================================================

@auth_bp.route('/api/register', methods=['POST'])
def register():
    """
    Register a new user account.
    
    Expected JSON body:
        - email, password, first_name, last_name, role
        - phone, date_of_birth (optional), gender (optional)
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    # Validate required fields
    required = ['email', 'password', 'first_name', 'last_name']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'{field} is required'}), 400
    
    # Check if email already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'success': False, 'error': 'Email already registered'}), 409
    
    # Validate password length
    if len(data['password']) < 6:
        return jsonify({'success': False, 'error': 'Password must be at least 6 characters'}), 400
    
    # Validate role
    role = data.get('role', 'patient')
    if role not in ['patient', 'doctor', 'admin']:
        role = 'patient'

    # Ensure doctor registrations come only from verified flow
    if role == 'doctor':
        doctor_verified = session.get('doctor_verified', False)
        verification_method = session.get('doctor_verification_method')
        verified_email = session.get('doctor_verified_email')
        request_email = (data.get('email') or '').strip().lower()

        if not doctor_verified or verification_method != 'both':
            return jsonify({
                'success': False,
                'error': 'Doctor verification (email + ID scan) required before registration'
            }), 403

        if request_email != verified_email:
            return jsonify({
                'success': False,
                'error': 'Registered email must match verified doctor email'
            }), 403

    # Validate gender - only accept valid values or None
    gender = data.get('gender')
    if gender not in ['male', 'female', 'other']:
        gender = None
    
    # Create new user
    user = User(
        email=data['email'],
        first_name=data['first_name'],
        last_name=data['last_name'],
        role=role,
        phone=data.get('phone', ''),
        gender=gender,
        address=data.get('address', '')
    )
    
    # Parse and set date of birth
    if data.get('date_of_birth'):
        try:
            user.date_of_birth = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
            user.calculate_senior_citizen()
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.flush()  # Get user ID before creating doctor profile
    
    # Create doctor profile if registering as doctor
    if role == 'doctor':
        specialty = data.get('specialty', '')
        if not specialty:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Please select your specialty'}), 400
        
        # Find department by name
        department = Department.query.filter_by(name=specialty).first()
        if not department:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Invalid specialty selected'}), 400
        
        doctor = Doctor(
            user_id=user.id,
            department_id=department.id,
            specialization=specialty
        )
        db.session.add(doctor)
    
    db.session.commit()

    if role == 'doctor':
        session.pop('doctor_verified', None)
        session.pop('doctor_verification_method', None)
        session.pop('doctor_verified_email', None)
        session.pop('doctor_verified_first_name', None)
        session.pop('doctor_verified_last_name', None)
    
    return jsonify({
        'success': True,
        'message': 'Registration successful! Please login.',
        'user': user.to_dict()
    }), 201


@auth_bp.route('/api/login', methods=['POST'])
def login():
    """
    Authenticate user and create session.
    
    Expected JSON body:
        - email, password, role (optional - for validation)
    """
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'success': False, 'error': 'Email and password required'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401
    
    if not user.is_active:
        return jsonify({'success': False, 'error': 'Account is deactivated. Contact admin.'}), 403
    
    # Check if user is trying to login with wrong role portal
    expected_role = data.get('role')
    if expected_role and expected_role != user.role:
        role_portals = {
            'patient': 'Patient',
            'doctor': 'Doctor', 
            'admin': 'Admin'
        }
        user_portal = role_portals.get(user.role, user.role.capitalize())
        return jsonify({
            'success': False, 
            'error': f'This account is registered as {user_portal}. Please login from the {user_portal} portal.',
            'correct_role': user.role
        }), 403
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Login user with Flask-Login
    login_user(user, remember=True)
    
    # Determine redirect URL based on role
    redirect_url = {
        'patient': '/patient/dashboard',
        'doctor': '/doctor/dashboard',
        'admin': '/admin/dashboard'
    }.get(user.role, '/')
    
    return jsonify({
        'success': True,
        'message': f'Welcome, {user.full_name}!',
        'user': user.to_dict(),
        'redirect': redirect_url
    })


@auth_bp.route('/api/logout', methods=['POST'])
@login_required
def logout():
    """Logout current user and destroy session."""
    logout_user()
    return jsonify({
        'success': True,
        'message': 'Logged out successfully',
        'redirect': url_for('auth.select_role_page')
    })


@auth_bp.route('/logout')
@login_required
def logout_page():
    """Logout and redirect to role selection."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.select_role_page'))


# ============================================================
# Utility function
# ============================================================
def redirect_by_role():
    """Redirect authenticated user to their role-specific dashboard."""
    if current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif current_user.role == 'doctor':
        return redirect(url_for('doctor.dashboard'))
    else:
        return redirect(url_for('patient.dashboard'))
