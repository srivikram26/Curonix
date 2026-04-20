# ============================================================
# Admin Routes
# Handles admin dashboard, doctor management, analytics
# ============================================================

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, time, timedelta
from sqlalchemy import func
from app.factory import db
from app.models import (
    Appointment, AppointmentHistory, Doctor, DoctorAvailability, Department,
    User, Notification, WaitingTimeLog, SystemSetting
)
from secrets import token_urlsafe
from app.ai_scheduler import scheduler
from app.routes.auth_routes import role_required

admin_bp = Blueprint('admin', __name__)


# ============================================================
# Page Routes
# ============================================================

@admin_bp.route('/dashboard')
@role_required('admin')
def dashboard():
    """Admin dashboard page."""
    return render_template('admin/dashboard.html')


@admin_bp.route('/doctors')
@role_required('admin')
def doctors_page():
    """Manage doctors page."""
    return render_template('admin/doctors.html')


@admin_bp.route('/departments')
@role_required('admin')
def departments_page():
    """Manage departments page."""
    return render_template('admin/departments.html')


@admin_bp.route('/analytics')
@role_required('admin')
def analytics_page():
    """Analytics dashboard page."""
    return render_template('admin/analytics.html')


@admin_bp.route('/appointments')
@role_required('admin')
def appointments_page():
    """All appointments management page."""
    return render_template('admin/appointments.html')


@admin_bp.route('/profile')
@role_required('admin')
def profile_page():
    """Admin profile page."""
    return render_template('admin/profile.html')


# ============================================================
# API Routes
# ============================================================

@admin_bp.route('/api/dashboard-data')
@role_required('admin')
def get_dashboard_data():
    """Get admin dashboard summary data."""
    today = date.today()
    
    # Counts
    total_patients = User.query.filter_by(role='patient').count()
    total_doctors = Doctor.query.count()
    total_departments = Department.query.filter_by(is_active=True).count()
    
    # Today's appointments
    today_appts = Appointment.query.filter(
        Appointment.appointment_date == today
    ).count()
    
    today_completed = Appointment.query.filter(
        Appointment.appointment_date == today,
        Appointment.status == 'completed'
    ).count()
    
    today_pending = Appointment.query.filter(
        Appointment.appointment_date == today,
        Appointment.status.in_(['scheduled', 'confirmed'])
    ).count()
    
    # This month's stats
    month_start = today.replace(day=1)
    month_appts = Appointment.query.filter(
        Appointment.appointment_date >= month_start
    ).count()
    
    # Emergency count today
    emergencies = Appointment.query.filter(
        Appointment.appointment_date == today,
        Appointment.priority == 'emergency'
    ).count()
    
    activity_window_start = today - timedelta(days=7)
    patient_activity = db.session.query(
        Appointment.status,
        func.count(Appointment.id)
    ).filter(
        Appointment.appointment_date >= activity_window_start
    ).group_by(Appointment.status).all()

    doc_activity_stmt = db.session.query(
        Doctor,
        func.count(Appointment.id).label('appointment_count')
    ).join(
        Appointment, Appointment.doctor_id == Doctor.id
    ).filter(
        Appointment.appointment_date >= activity_window_start
    ).group_by(Doctor.id).order_by(func.count(Appointment.id).desc()).limit(5).all()

    # AI scheduling stats
    ai_stats = scheduler.get_scheduling_analytics(30)
    
    # Department-wise breakdown
    dept_stats = db.session.query(
        Department.name,
        func.count(Appointment.id)
    ).join(
        Appointment, Appointment.department_id == Department.id
    ).filter(
        Appointment.appointment_date >= month_start
    ).group_by(Department.name).all()
    
    # Recent appointments
    recent = Appointment.query.order_by(
        Appointment.created_at.desc()
    ).limit(10).all()
    
    return jsonify({
        'success': True,
        'overview': {
            'total_patients': total_patients,
            'total_doctors': total_doctors,
            'total_departments': total_departments,
            'today_appointments': today_appts,
            'today_completed': today_completed,
            'today_pending': today_pending,
            'month_appointments': month_appts,
            'emergencies_today': emergencies
        },
        'ai_analytics': ai_stats,
        'department_stats': [{'name': name, 'count': count} for name, count in dept_stats],
        'recent_appointments': [a.to_dict() for a in recent],
        'patient_activity': [
            {'status': status or 'unknown', 'count': count}
            for status, count in patient_activity
        ],
        'doctor_activity': [
            {
                'doctor': doc.full_name,
                'department': doc.department.name if doc.department else 'General',
                'count': appointment_count
            }
            for doc, appointment_count in doc_activity_stmt
        ]
    })


@admin_bp.route('/api/profile', methods=['PUT'])
@role_required('admin')
def update_profile():
    """Update current admin profile."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    user = User.query.get(current_user.id)

    if data.get('first_name'):
        user.first_name = data['first_name'].strip()
    if data.get('last_name'):
        user.last_name = data['last_name'].strip()

    if data.get('phone') is not None:
        user.phone = str(data['phone']).strip()

    if data.get('address') is not None:
        user.address = str(data['address']).strip()

    if data.get('date_of_birth') is not None:
        dob_value = str(data['date_of_birth']).strip()
        if dob_value:
            try:
                user.date_of_birth = datetime.strptime(dob_value, '%Y-%m-%d').date()
                user.calculate_senior_citizen()
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            user.date_of_birth = None
            user.is_senior_citizen = False

    if data.get('gender') is not None:
        gender_value = str(data['gender']).strip().lower()
        user.gender = gender_value if gender_value in ['male', 'female', 'other'] else None

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Profile updated successfully',
        'user': user.to_dict()
    })


@admin_bp.route('/api/add-doctor', methods=['POST'])
@role_required('admin')
def add_doctor():
    """
    Add a new doctor to the system.
    
    Expected JSON:
        - email, password, first_name, last_name
        - department_id, specialization, qualification
        - experience_years, consultation_fee, phone
        - address (optional hospital branch)
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    required = ['email', 'password', 'first_name', 'last_name', 'department_id']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'{field} is required'}), 400
    
    # Check email uniqueness
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'success': False, 'error': 'Email already registered'}), 409
    
    # Verify department exists
    department = Department.query.get(data['department_id'])
    if not department:
        return jsonify({'success': False, 'error': 'Department not found'}), 404
    
    # Create user account
    user = User(
        email=data['email'],
        first_name=data['first_name'],
        last_name=data['last_name'],
        role='doctor',
        phone=data.get('phone', ''),
        gender=data.get('gender'),
        address=data.get('address', 'Main Campus Hospital')
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.flush()  # Get user.id before committing
    
    # Create doctor profile
    doctor = Doctor(
        user_id=user.id,
        department_id=int(data['department_id']),
        specialization=data.get('specialization', ''),
        qualification=data.get('qualification', ''),
        experience_years=int(data.get('experience_years', 0)),
        consultation_fee=float(data.get('consultation_fee', 0)),
        max_patients_per_day=int(data.get('max_patients_per_day', 20)),
        avg_consultation_time=int(data.get('avg_consultation_time', 30)),
        bio=data.get('bio', '')
    )
    db.session.add(doctor)
    db.session.flush()
    
    # Set default availability (Mon-Fri, 9 AM - 5 PM)
    for day in range(5):  # Monday to Friday
        avail = DoctorAvailability(
            doctor_id=doctor.id,
            day_of_week=day,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_available=True
        )
        db.session.add(avail)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Dr. {user.full_name} added successfully',
        'doctor': doctor.to_dict()
    }), 201


@admin_bp.route('/api/doctors')
@role_required('admin')
def get_all_doctors():
    """Get all doctors with their details."""
    doctors = Doctor.query.all()
    return jsonify({
        'success': True,
        'doctors': [d.to_dict() for d in doctors]
    })


@admin_bp.route('/api/doctors/<int:doctor_id>', methods=['PUT'])
@role_required('admin')
def update_doctor(doctor_id):
    """Update doctor details."""
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor not found'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    if data.get('specialization'):
        doctor.specialization = data['specialization']
    if data.get('qualification'):
        doctor.qualification = data['qualification']
    if data.get('experience_years') is not None:
        doctor.experience_years = int(data['experience_years'])
    if data.get('consultation_fee') is not None:
        doctor.consultation_fee = float(data['consultation_fee'])
    if data.get('max_patients_per_day') is not None:
        doctor.max_patients_per_day = int(data['max_patients_per_day'])
    if data.get('department_id'):
        doctor.department_id = int(data['department_id'])
    if data.get('is_active') is not None:
        doctor.user.is_active = bool(data['is_active'])
    if data.get('address'):
        doctor.user.address = data['address']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Doctor updated successfully',
        'doctor': doctor.to_dict()
    })


@admin_bp.route('/api/doctors/<int:doctor_id>/reset-password', methods=['POST'])
@role_required('admin')
def reset_doctor_password(doctor_id):
    """Generate a temporary password for a doctor account."""
    doctor = Doctor.query.get(doctor_id)
    if not doctor or not doctor.user:
        return jsonify({'success': False, 'error': 'Doctor not found'}), 404
    temp_password = token_urlsafe(6)
    doctor.user.set_password(temp_password)
    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Temporary password generated',
        'temporary_password': temp_password
    })


@admin_bp.route('/api/doctors/<int:doctor_id>', methods=['DELETE'])
@role_required('admin')
def deactivate_doctor(doctor_id):
    """Deactivate a doctor account."""
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor not found'}), 404
    
    doctor.user.is_active = False
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Doctor account deactivated'})


# ============================================================
# Department Management
# ============================================================

@admin_bp.route('/api/departments', methods=['GET'])
@role_required('admin')
def get_departments():
    """Get all departments."""
    departments = Department.query.order_by(Department.is_active.desc(), Department.name.asc()).all()
    return jsonify({
        'success': True,
        'departments': [d.to_dict() for d in departments]
    })


@admin_bp.route('/api/departments', methods=['POST'])
@role_required('admin')
def add_department():
    """
    Add a new department.
    
    Expected JSON:
        - name, description (optional), floor_number (optional)
    """
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'success': False, 'error': 'Department name is required'}), 400
    
    if Department.query.filter_by(name=data['name']).first():
        return jsonify({'success': False, 'error': 'Department already exists'}), 409
    
    dept = Department(
        name=data['name'],
        description=data.get('description', ''),
        floor_number=int(data.get('floor_number', 1))
    )
    db.session.add(dept)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Department added successfully',
        'department': dept.to_dict()
    }), 201


@admin_bp.route('/api/departments/<int:dept_id>', methods=['PUT'])
@role_required('admin')
def update_department(dept_id):
    """Update a department."""
    dept = Department.query.get(dept_id)
    if not dept:
        return jsonify({'success': False, 'error': 'Department not found'}), 404
    
    data = request.get_json()
    if data.get('name'):
        dept.name = data['name']
    if data.get('description') is not None:
        dept.description = data['description']
    if data.get('floor_number') is not None:
        dept.floor_number = int(data['floor_number'])
    if data.get('is_active') is not None:
        dept.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Department updated',
        'department': dept.to_dict()
    })


@admin_bp.route('/api/departments/<int:dept_id>', methods=['DELETE'])
@role_required('admin')
def delete_department(dept_id):
    """Soft-delete a department."""
    dept = Department.query.get(dept_id)
    if not dept:
        return jsonify({'success': False, 'error': 'Department not found'}), 404

    dept.is_active = False
    db.session.commit()

    return jsonify({'success': True, 'message': 'Department deleted'})


# ============================================================
# Analytics
# ============================================================

@admin_bp.route('/api/analytics')
@role_required('admin')
def get_analytics():
    """Get comprehensive analytics data."""
    days = int(request.args.get('days', 30))
    cutoff = date.today() - timedelta(days=days)
    cutoff_start = datetime.combine(cutoff, time.min)
    
    # Scheduling analytics from AI
    scheduling_stats = scheduler.get_scheduling_analytics(days)
    
    # Peak hours analysis
    peak_data = scheduler.analyze_peak_hours(days_back=days)
    hourly_distribution = peak_data.get('hourly_distribution') or {}
    peak_hours = [
        {'hour': hour, 'count': count}
        for hour, count in sorted(hourly_distribution.items())
    ]
    
    # Daily appointment trend (last N days)
    daily_trend_records = db.session.query(
        Appointment.appointment_date,
        func.count(Appointment.id)
    ).filter(
        Appointment.appointment_date >= cutoff
    ).group_by(Appointment.appointment_date).order_by(
        Appointment.appointment_date
    ).all()
    daily_trends = [
        {'date': d.isoformat(), 'count': c} for d, c in daily_trend_records
    ]
    
    # Priority distribution
    priority_dist = db.session.query(
        Appointment.priority,
        func.count(Appointment.id)
    ).filter(
        Appointment.created_at >= cutoff_start
    ).group_by(Appointment.priority).all()
    
    # Doctor workload comparison
    doctors = Doctor.query.all()
    doctor_workloads = []
    for doc in doctors:
        count = Appointment.query.filter(
            Appointment.doctor_id == doc.id,
            Appointment.appointment_date >= cutoff,
            Appointment.status.in_(['completed', 'scheduled', 'confirmed'])
        ).count()
        max_capacity = doc.max_patients_per_day * days
        workload_ratio = round(count / max_capacity, 2) if max_capacity > 0 else 0
        doctor_workloads.append({
            'doctor_name': doc.full_name,
            'department': doc.department.name if doc.department else 'General',
            'appointments': count,
            'max_capacity': max_capacity,
            'workload_ratio': workload_ratio,
            'utilization': round(workload_ratio * 100, 1)
        })
    
    # Conflict detection for today
    conflict_date = date.today()
    conflicts = []
    for doc in doctors:
        doc_conflicts = scheduler.detect_conflicts(doc.id, conflict_date)
        for conflict in doc_conflicts:
            conflicts.append({
                'type': conflict.get('type', 'Conflict').capitalize(),
                'doctor_name': doc.full_name,
                'date': conflict_date.isoformat(),
                'details': conflict.get('message'),
                'severity': conflict.get('severity', 'medium').capitalize()
            })

    # Auto-rescheduling count from history
    auto_rescheduled_count = AppointmentHistory.query.filter(
        AppointmentHistory.change_reason.ilike('%Auto-rescheduled by AI%'),
        AppointmentHistory.created_at >= cutoff_start
    ).count()

    scheduling_stats_payload = dict(scheduling_stats)
    scheduling_stats_payload.update({
        'ai_scheduled': scheduling_stats.get('ai_scheduled_count', 0),
        'avg_waiting_time': scheduling_stats.get('avg_wait_time', 0),
        'conflicts_detected': len(conflicts),
        'auto_rescheduled': auto_rescheduled_count
    })
    
    return jsonify({
        'success': True,
        'scheduling_stats': scheduling_stats_payload,
        'peak_hours': peak_hours,
        'daily_trend': daily_trends,
        'daily_trends': daily_trends,
        'priority_distribution': [
            {'priority': p or 'normal', 'count': c} for p, c in priority_dist
        ],
        'doctor_workloads': sorted(
            doctor_workloads, key=lambda x: x['appointments'], reverse=True
        ),
        'conflicts': conflicts
    })


@admin_bp.route('/api/emergency-override', methods=['POST'])
@role_required('admin')
def emergency_override():
    """
    Admin emergency override scheduling.
    Bypasses normal constraints to schedule an urgent appointment.
    
    Expected JSON:
        - patient_id, doctor_id, department_id
        - date, time, symptoms
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    required = ['patient_id', 'doctor_id', 'department_id', 'date']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'{field} is required'}), 400
    
    try:
        appt_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date format'}), 400
    
    appt_time = None
    if data.get('time'):
        try:
            appt_time = datetime.strptime(data['time'], '%H:%M').time()
        except ValueError:
            appt_time = datetime.now().time()
    else:
        appt_time = datetime.now().time()
    
    # Force-schedule emergency (bypasses capacity and leave checks)
    location = (data.get('location') or '').strip() or 'Main Campus Hospital'
    result = scheduler.schedule_appointment(
        patient_id=int(data['patient_id']),
        department_id=int(data['department_id']),
        preferred_date=appt_date,
        preferred_time=appt_time,
        appointment_type='emergency',
        preferred_doctor_id=int(data['doctor_id']),
        symptoms=data.get('symptoms', 'Emergency - Admin Override'),
        notes=f'Emergency override by admin {current_user.full_name}',
        location=location
    )
    
    return jsonify(result)


@admin_bp.route('/api/all-appointments')
@role_required('admin')
def get_all_appointments():
    """Get all appointments with filters."""
    status = request.args.get('status', 'all')
    dept_id = request.args.get('department_id')
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    query = Appointment.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    if dept_id:
        query = query.filter_by(department_id=int(dept_id))
    if date_from_str:
        try:
            start_date = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            query = query.filter(Appointment.appointment_date >= start_date)
        except ValueError:
            pass
    if date_to_str:
        try:
            end_date = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            query = query.filter(Appointment.appointment_date <= end_date)
        except ValueError:
            pass
    
    total = query.count()
    appointments = query.order_by(
        Appointment.appointment_date.desc(),
        Appointment.start_time.desc()
    ).offset((page - 1) * per_page).limit(per_page).all()
    
    return jsonify({
        'success': True,
        'appointments': [a.to_dict() for a in appointments],
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    })


@admin_bp.route('/api/patients')
@role_required('admin')
def get_all_patients():
    """Get all registered patients."""
    patients = User.query.filter_by(role='patient').order_by(User.created_at.desc()).all()
    return jsonify({
        'success': True,
        'patients': [p.to_dict() for p in patients]
    })
