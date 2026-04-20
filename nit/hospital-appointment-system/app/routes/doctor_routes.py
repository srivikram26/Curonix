# ============================================================
# Doctor Routes
# Handles doctor dashboard, schedule, availability, patients
# ============================================================

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, time, timedelta
from sqlalchemy import func
from app.factory import db
from app.models import (
    Appointment, Doctor, DoctorAvailability, DoctorLeave,
    User, Notification, AppointmentHistory
)
from app.ai_scheduler import scheduler
from app.routes.auth_routes import role_required

doctor_bp = Blueprint('doctor', __name__)


# ============================================================
# Page Routes
# ============================================================

@doctor_bp.route('/dashboard')
@role_required('doctor')
def dashboard():
    """Doctor dashboard page."""
    return render_template('doctor/dashboard.html')


@doctor_bp.route('/schedule')
@role_required('doctor')
def schedule_page():
    """Doctor schedule view."""
    return render_template('doctor/schedule.html')


@doctor_bp.route('/availability')
@role_required('doctor')
def availability_page():
    """Manage availability page."""
    return render_template('doctor/availability.html')


@doctor_bp.route('/patients')
@role_required('doctor')
def patients_page():
    """View patient history."""
    return render_template('doctor/patients.html')


@doctor_bp.route('/profile')
@role_required('doctor')
def profile_page():
    """Doctor profile page."""
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    return render_template('doctor/profile.html', doctor=doctor)


# ============================================================
# API Routes
# ============================================================

@doctor_bp.route('/api/dashboard-data')
@role_required('doctor')
def get_dashboard_data():
    """Get doctor dashboard summary."""
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor profile not found'}), 404
    
    today = date.today()
    
    # Today's appointments
    today_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date == today,
        Appointment.status.in_(['scheduled', 'confirmed', 'in_progress'])
    ).order_by(Appointment.start_time).all()
    
    # This week's count
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_count = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date.between(week_start, week_end),
        Appointment.status.in_(['scheduled', 'confirmed', 'in_progress', 'completed'])
    ).count()
    
    # Total patients seen
    total_patients = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.status == 'completed'
    ).count()
    
    # Pending appointments
    pending = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date >= today,
        Appointment.status.in_(['scheduled', 'confirmed'])
    ).count()
    
    # Emergency cases today
    emergencies_today = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date == today,
        Appointment.priority == 'emergency'
    ).count()
    
    # Conflicts
    conflicts = scheduler.detect_conflicts(doctor.id, today)
    
    return jsonify({
        'success': True,
        'doctor': doctor.to_dict(),
        'today_appointments': [a.to_dict() for a in today_appointments],
        'stats': {
            'today_count': len(today_appointments),
            'week_count': week_count,
            'total_patients': total_patients,
            'pending': pending,
            'emergencies_today': emergencies_today,
            'workload_ratio': round(doctor.get_workload_ratio(today) * 100, 1)
        },
        'conflicts': conflicts
    })


@doctor_bp.route('/api/schedule')
@role_required('doctor')
def get_schedule():
    """
    Get doctor's schedule for a specific date.
    
    Query params:
        - date (str: YYYY-MM-DD, optional, defaults to today)
    """
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor profile not found'}), 404
    
    date_str = request.args.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()
    
    appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date == target_date
    ).order_by(Appointment.priority_score.desc(), Appointment.start_time).all()
    
    return jsonify({
        'success': True,
        'date': target_date.isoformat(),
        'appointments': [a.to_dict() for a in appointments],
        'total': len(appointments)
    })


@doctor_bp.route('/api/weekly-schedule')
@role_required('doctor')
def get_weekly_schedule():
    """Get doctor's schedule for the current week."""
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor profile not found'}), 404
    
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    
    weekly_data = {}
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_name = day.strftime('%A')
        
        appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == day,
            Appointment.status.in_(['scheduled', 'confirmed', 'in_progress', 'completed'])
        ).order_by(Appointment.start_time).all()
        
        weekly_data[day_name] = {
            'date': day.isoformat(),
            'appointments': [a.to_dict() for a in appointments],
            'count': len(appointments)
        }
    
    return jsonify({
        'success': True,
        'week_start': week_start.isoformat(),
        'schedule': weekly_data
    })


@doctor_bp.route('/api/patients')
@role_required('doctor')
def get_patients():
    """Return unique patients seen by the logged-in doctor."""
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor profile not found'}), 404

    patient_counts = db.session.query(
        Appointment.patient_id,
        func.count(Appointment.id).label('total_visits')
    ).filter(
        Appointment.doctor_id == doctor.id
    ).group_by(Appointment.patient_id).all()

    patient_ids = [pc.patient_id for pc in patient_counts]
    patients = []
    if patient_ids:
        users = User.query.filter(User.id.in_(patient_ids)).all()
        user_map = {u.id: u for u in users}
        for patient_id, total_visits in patient_counts:
            user = user_map.get(patient_id)
            if not user:
                continue
            patients.append({
                'id': user.id,
                'name': user.full_name,
                'email': user.email,
                'phone': user.phone,
                'age': user.age,
                'is_senior': user.is_senior_citizen,
                'total_visits': total_visits
            })

    return jsonify({'success': True, 'patients': patients})


@doctor_bp.route('/api/patient-history/<int:patient_id>')
@role_required('doctor')
def patient_history(patient_id):
    """Get appointment history for a single patient filtered by doctor."""
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor profile not found'}), 404

    appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.patient_id == patient_id
    ).order_by(
        Appointment.appointment_date.desc(),
        Appointment.start_time.desc()
    ).all()

    history = [
        {
            'date': a.appointment_date.isoformat() if a.appointment_date else None,
            'start_time': a.start_time.strftime('%H:%M') if a.start_time else None,
            'appointment_type': a.appointment_type,
            'priority': (a.priority or 'normal').title(),
            'status': (a.status or 'unknown').replace('_', ' ').title(),
            'symptoms': a.symptoms,
            'notes': a.notes
        }
        for a in appointments
    ]

    return jsonify({'success': True, 'appointments': history})


@doctor_bp.route('/api/profile', methods=['PUT'])
@role_required('doctor')
def update_profile():
    """Update current doctor's profile details."""
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor profile not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    user = doctor.user

    if data.get('first_name'):
        user.first_name = data['first_name'].strip()
    if data.get('last_name'):
        user.last_name = data['last_name'].strip()
    if data.get('phone') is not None:
        user.phone = str(data['phone']).strip()
    if data.get('address') is not None:
        user.address = str(data['address']).strip()

    if data.get('specialization') is not None:
        doctor.specialization = str(data['specialization']).strip()
    if data.get('qualification') is not None:
        doctor.qualification = str(data['qualification']).strip()
    if data.get('bio') is not None:
        doctor.bio = str(data['bio']).strip()

    if data.get('experience_years') is not None:
        try:
            experience_years = int(data['experience_years'])
            if experience_years < 0:
                return jsonify({'success': False, 'error': 'Experience years cannot be negative'}), 400
            doctor.experience_years = experience_years
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Experience years must be a valid number'}), 400

    if data.get('consultation_fee') is not None:
        try:
            consultation_fee = float(data['consultation_fee'])
            if consultation_fee < 0:
                return jsonify({'success': False, 'error': 'Consultation fee cannot be negative'}), 400
            doctor.consultation_fee = consultation_fee
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Consultation fee must be a valid number'}), 400

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Profile updated successfully',
        'doctor': doctor.to_dict(),
        'user': user.to_dict()
    })


@doctor_bp.route('/api/availability', methods=['GET'])
@role_required('doctor')
def get_availability():
    """Get doctor's weekly availability settings."""
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor profile not found'}), 404
    
    availability = DoctorAvailability.query.filter_by(doctor_id=doctor.id).all()
    
    return jsonify({
        'success': True,
        'availability': [a.to_dict() for a in availability]
    })


@doctor_bp.route('/api/availability', methods=['POST'])
@role_required('doctor')
def update_availability():
    """
    Update doctor's weekly availability.
    
    Expected JSON:
        - slots: list of {day_of_week, start_time, end_time, is_available}
    """
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor profile not found'}), 404
    
    data = request.get_json()
    if not data or 'slots' not in data:
        return jsonify({'success': False, 'error': 'Slots data required'}), 400
    
    # Clear existing availability
    DoctorAvailability.query.filter_by(doctor_id=doctor.id).delete()
    
    for slot in data['slots']:
        avail = DoctorAvailability(
            doctor_id=doctor.id,
            day_of_week=int(slot['day_of_week']),
            start_time=datetime.strptime(slot['start_time'], '%H:%M').time(),
            end_time=datetime.strptime(slot['end_time'], '%H:%M').time(),
            is_available=slot.get('is_available', True)
        )
        db.session.add(avail)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Availability updated successfully'})


@doctor_bp.route('/api/update-status/<int:appointment_id>', methods=['POST'])
@role_required('doctor')
def update_appointment_status(appointment_id):
    """
    Update appointment status (mark as in-progress, completed, etc.)
    
    Expected JSON:
        - status: new status string
        - notes: optional doctor notes
    """
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor profile not found'}), 404
    
    appointment = Appointment.query.filter_by(
        id=appointment_id,
        doctor_id=doctor.id
    ).first()
    
    if not appointment:
        return jsonify({'success': False, 'error': 'Appointment not found'}), 404
    
    data = request.get_json()
    if not data or not data.get('status'):
        return jsonify({'success': False, 'error': 'Status is required'}), 400
    
    old_status = appointment.status
    new_status = data['status']
    
    valid_statuses = ['confirmed', 'in_progress', 'completed', 'no_show']
    if new_status not in valid_statuses:
        return jsonify({'success': False, 'error': f'Invalid status. Must be one of: {valid_statuses}'}), 400
    
    appointment.status = new_status
    
    if data.get('notes'):
        appointment.notes = data['notes']
    
    # Record actual wait time when marking in-progress
    if new_status == 'in_progress' and appointment.start_time:
        now = datetime.now().time()
        scheduled_minutes = appointment.start_time.hour * 60 + appointment.start_time.minute
        actual_minutes = now.hour * 60 + now.minute
        appointment.actual_wait_time = max(0, actual_minutes - scheduled_minutes)
    
    # Record history
    history = AppointmentHistory(
        appointment_id=appointment.id,
        changed_by=current_user.id,
        old_status=old_status,
        new_status=new_status,
        change_reason=data.get('notes', f'Status updated by doctor')
    )
    db.session.add(history)
    
    # Notify patient
    notification = Notification(
        user_id=appointment.patient_id,
        appointment_id=appointment.id,
        type='system',
        subject=f'Appointment {new_status.replace("_", " ").title()}',
        message=f'Your appointment status has been updated to: {new_status.replace("_", " ").title()}'
    )
    db.session.add(notification)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Appointment status updated to {new_status}',
        'appointment': appointment.to_dict()
    })


@doctor_bp.route('/api/emergency-slot', methods=['POST'])
@role_required('doctor')
def handle_emergency():
    """
    Schedule an emergency appointment (overrides normal scheduling).
    
    Expected JSON:
        - patient_id, symptoms, notes
    """
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor profile not found'}), 404
    
    data = request.get_json()
    if not data or not data.get('patient_id'):
        return jsonify({'success': False, 'error': 'Patient ID is required'}), 400
    
    location = (data.get('location') or '').strip() or 'Main Campus Hospital'
    # Schedule emergency using AI (highest priority)
    result = scheduler.schedule_appointment(
        patient_id=int(data['patient_id']),
        department_id=doctor.department_id,
        preferred_date=date.today(),
        preferred_time=datetime.now().time(),
        appointment_type='emergency',
        preferred_doctor_id=doctor.id,
        symptoms=data.get('symptoms', 'Emergency case'),
        notes=data.get('notes', ''),
        location=location
    )
    
    return jsonify(result)


@doctor_bp.route('/api/patient-history/<int:patient_id>')
@role_required('doctor')
def get_patient_history(patient_id):
    """Get appointment history for a specific patient."""
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor profile not found'}), 404
    
    patient = User.query.get(patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    
    # Get appointments with this doctor
    appointments = Appointment.query.filter(
        Appointment.patient_id == patient_id,
        Appointment.doctor_id == doctor.id
    ).order_by(Appointment.appointment_date.desc()).all()
    
    return jsonify({
        'success': True,
        'patient': patient.to_dict(),
        'appointments': [a.to_dict() for a in appointments]
    })


@doctor_bp.route('/api/leave', methods=['POST'])
@role_required('doctor')
def request_leave():
    """
    Mark a leave date.
    
    Expected JSON:
        - date: YYYY-MM-DD
        - reason: optional
    """
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor profile not found'}), 404
    
    data = request.get_json()
    if not data or not data.get('date'):
        return jsonify({'success': False, 'error': 'Leave date is required'}), 400
    
    try:
        leave_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date format'}), 400
    
    # Check for existing leave
    existing = DoctorLeave.query.filter_by(
        doctor_id=doctor.id, leave_date=leave_date
    ).first()
    
    if existing:
        return jsonify({'success': False, 'error': 'Leave already marked for this date'}), 409
    
    leave = DoctorLeave(
        doctor_id=doctor.id,
        leave_date=leave_date,
        reason=data.get('reason', '')
    )
    db.session.add(leave)
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Leave marked for {leave_date}'})
