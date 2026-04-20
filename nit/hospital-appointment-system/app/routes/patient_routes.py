# ============================================================
# Patient Routes
# Handles patient dashboard, booking, cancellation, history
# ============================================================

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, time, timedelta
from app.factory import db
from app.models import (
    Appointment, Doctor, Department, User,
    Notification, AppointmentHistory
)
from app.ai_scheduler import scheduler
from app.routes.auth_routes import role_required

patient_bp = Blueprint('patient', __name__)


# ============================================================
# Page Routes
# ============================================================

@patient_bp.route('/dashboard')
@role_required('patient')
def dashboard():
    """Patient dashboard page."""
    return render_template('patient/dashboard.html')


@patient_bp.route('/book')
@role_required('patient')
def book_appointment_page():
    """Appointment booking page."""
    return render_template('patient/book_appointment.html')


@patient_bp.route('/appointments')
@role_required('patient')
def appointments_page():
    """View all appointments page."""
    return render_template('patient/appointments.html')


@patient_bp.route('/profile')
@role_required('patient')
def profile_page():
    """Patient profile page."""
    return render_template('patient/profile.html')


# ============================================================
# API Routes
# ============================================================

@patient_bp.route('/api/dashboard-data')
@role_required('patient')
def get_dashboard_data():
    """
    Get patient dashboard summary data.
    
    Returns upcoming appointments, recent history, and statistics.
    """
    today = date.today()
    
    # Upcoming appointments
    upcoming = Appointment.query.filter(
        Appointment.patient_id == current_user.id,
        Appointment.appointment_date >= today,
        Appointment.status.in_(['scheduled', 'confirmed'])
    ).order_by(Appointment.appointment_date, Appointment.start_time).limit(5).all()
    
    # Recent completed appointments
    recent = Appointment.query.filter(
        Appointment.patient_id == current_user.id,
        Appointment.status == 'completed'
    ).order_by(Appointment.appointment_date.desc()).limit(5).all()
    
    # Statistics
    total_appointments = Appointment.query.filter_by(patient_id=current_user.id).count()
    completed_count = Appointment.query.filter_by(
        patient_id=current_user.id, status='completed'
    ).count()
    cancelled_count = Appointment.query.filter_by(
        patient_id=current_user.id, status='cancelled'
    ).count()
    
    # Unread notifications
    unread_notifs = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    
    return jsonify({
        'success': True,
        'upcoming': [a.to_dict() for a in upcoming],
        'recent': [a.to_dict() for a in recent],
        'stats': {
            'total': total_appointments,
            'completed': completed_count,
            'cancelled': cancelled_count,
            'upcoming_count': len(upcoming)
        },
        'unread_notifications': unread_notifs,
        'user': current_user.to_dict()
    })


@patient_bp.route('/api/departments')
@role_required('patient')
def get_departments():
    """Get all active departments."""
    departments = Department.query.filter_by(is_active=True).all()
    return jsonify({
        'success': True,
        'departments': [d.to_dict() for d in departments]
    })


@patient_bp.route('/api/doctors/<int:department_id>')
@role_required('patient')
def get_doctors_by_department(department_id):
    """Get all doctors in a department."""
    doctors = Doctor.query.filter_by(department_id=department_id).all()
    active_doctors = [d for d in doctors if d.user.is_active]
    return jsonify({
        'success': True,
        'doctors': [d.to_dict() for d in active_doctors]
    })


@patient_bp.route('/api/available-slots', methods=['POST'])
@role_required('patient')
def get_available_slots():
    """
    Get available time slots for booking.
    
    Expected JSON:
        - department_id (int)
        - date (str: YYYY-MM-DD)
        - doctor_id (int, optional)
    """
    data = request.get_json()
    
    if not data or not data.get('department_id') or not data.get('date'):
        return jsonify({'success': False, 'error': 'Department and date are required'}), 400
    
    try:
        target_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date format'}), 400
    
    if target_date < date.today():
        return jsonify({'success': False, 'error': 'Cannot book appointments in the past'}), 400
    
    doctor_id = data.get('doctor_id')
    slots = scheduler.get_available_slots_for_date(
        data['department_id'],
        target_date,
        doctor_id
    )
    
    return jsonify({
        'success': True,
        'slots': slots,
        'date': target_date.isoformat(),
        'total_available': len(slots)
    })


@patient_bp.route('/api/book', methods=['POST'])
@role_required('patient')
def book_appointment():
    """
    Book a new appointment using AI scheduler.
    
    Expected JSON:
        - department_id, date, time (required)
        - doctor_id (optional - AI will select if not provided)
        - appointment_type: 'new', 'follow_up', 'emergency'
        - symptoms, notes (optional)
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    required = ['department_id', 'date']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'{field} is required'}), 400
    
    try:
        preferred_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date format'}), 400
    
    preferred_time = None
    if data.get('time'):
        try:
            preferred_time = datetime.strptime(data['time'], '%H:%M').time()
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid time format. Use HH:MM'}), 400
    
    # Use AI Scheduler
    result = scheduler.schedule_appointment(
        patient_id=current_user.id,
        department_id=int(data['department_id']),
        preferred_date=preferred_date,
        preferred_time=preferred_time,
        appointment_type=data.get('appointment_type', 'new'),
        preferred_doctor_id=int(data['doctor_id']) if data.get('doctor_id') else None,
        symptoms=data.get('symptoms', ''),
        notes=data.get('notes', '')
    )
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 400


@patient_bp.route('/api/appointments')
@role_required('patient')
def get_patient_appointments():
    """Get all appointments for the current patient."""
    status_filter = request.args.get('status', 'all')
    
    query = Appointment.query.filter_by(patient_id=current_user.id)
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    appointments = query.order_by(
        Appointment.appointment_date.desc(),
        Appointment.start_time.desc()
    ).all()
    
    return jsonify({
        'success': True,
        'appointments': [a.to_dict() for a in appointments]
    })


@patient_bp.route('/api/cancel/<int:appointment_id>', methods=['POST'])
@role_required('patient')
def cancel_appointment(appointment_id):
    """
    Cancel an appointment and trigger AI auto-rescheduling.
    
    Expected JSON:
        - reason (str, optional)
    """
    appointment = Appointment.query.filter_by(
        id=appointment_id,
        patient_id=current_user.id
    ).first()
    
    if not appointment:
        return jsonify({'success': False, 'error': 'Appointment not found'}), 404
    
    if appointment.status not in ['scheduled', 'confirmed']:
        return jsonify({'success': False, 'error': 'Cannot cancel this appointment'}), 400
    
    data = request.get_json() or {}
    
    # Record history
    old_status = appointment.status
    appointment.status = 'cancelled'
    appointment.cancellation_reason = data.get('reason', 'Cancelled by patient')
    
    history = AppointmentHistory(
        appointment_id=appointment.id,
        changed_by=current_user.id,
        old_status=old_status,
        new_status='cancelled',
        change_reason=data.get('reason', 'Cancelled by patient')
    )
    db.session.add(history)
    db.session.commit()
    
    # AI auto-rescheduling: shift later appointments forward
    rescheduled = scheduler.auto_reschedule_on_cancellation(appointment)
    
    return jsonify({
        'success': True,
        'message': 'Appointment cancelled successfully',
        'auto_rescheduled': rescheduled
    })


@patient_bp.route('/api/reschedule/<int:appointment_id>', methods=['POST'])
@role_required('patient')
def reschedule_appointment(appointment_id):
    """
    Reschedule an existing appointment.
    
    Expected JSON:
        - new_date (str: YYYY-MM-DD)
        - new_time (str: HH:MM, optional)
    """
    appointment = Appointment.query.filter_by(
        id=appointment_id,
        patient_id=current_user.id
    ).first()
    
    if not appointment:
        return jsonify({'success': False, 'error': 'Appointment not found'}), 404
    
    if appointment.status not in ['scheduled', 'confirmed']:
        return jsonify({'success': False, 'error': 'Cannot reschedule this appointment'}), 400
    
    data = request.get_json()
    if not data or not data.get('new_date'):
        return jsonify({'success': False, 'error': 'New date is required'}), 400
    
    try:
        new_date = datetime.strptime(data['new_date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date format'}), 400
    
    new_time = None
    if data.get('new_time'):
        try:
            new_time = datetime.strptime(data['new_time'], '%H:%M').time()
        except ValueError:
            pass
    
    # Cancel old appointment
    old_status = appointment.status
    old_date = appointment.appointment_date
    old_time = appointment.start_time
    appointment.status = 'rescheduled'
    
    # Book new appointment with AI
    result = scheduler.schedule_appointment(
        patient_id=current_user.id,
        department_id=appointment.department_id,
        preferred_date=new_date,
        preferred_time=new_time,
        appointment_type=appointment.appointment_type,
        preferred_doctor_id=appointment.doctor_id,
        symptoms=appointment.symptoms or '',
        notes=appointment.notes or '',
    )
    
    if result['success']:
        # Link rescheduled appointment to original
        new_appt = Appointment.query.get(result['appointment']['id'])
        if new_appt:
            new_appt.rescheduled_from = appointment_id
        
        # Record history
        history = AppointmentHistory(
            appointment_id=appointment_id,
            changed_by=current_user.id,
            old_status=old_status,
            new_status='rescheduled',
            old_date=old_date,
            new_date=new_date,
            old_time=old_time,
            new_time=new_time,
            change_reason=data.get('reason', 'Rescheduled by patient')
        )
        db.session.add(history)
        db.session.commit()
        
        # Auto-reschedule remaining appointments for freed slot
        scheduler.auto_reschedule_on_cancellation(appointment)
    
    return jsonify(result)


@patient_bp.route('/api/notifications')
@role_required('patient')
def get_notifications():
    """Get patient's notifications."""
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.sent_at.desc()).limit(20).all()
    
    return jsonify({
        'success': True,
        'notifications': [n.to_dict() for n in notifications]
    })


@patient_bp.route('/api/notifications/mark-read', methods=['POST'])
@role_required('patient')
def mark_notifications_read():
    """Mark all notifications as read."""
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'All notifications marked as read'})


@patient_bp.route('/api/profile', methods=['PUT'])
@role_required('patient')
def update_profile():
    """Update patient profile."""
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

    if data.get('blood_group') is not None:
        blood_value = str(data['blood_group']).strip().upper()
        allowed_bloods = {'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'}
        user.blood_group = blood_value if blood_value in allowed_bloods else None
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Profile updated successfully',
        'user': user.to_dict()
    })
