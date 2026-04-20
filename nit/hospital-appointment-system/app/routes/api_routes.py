# ============================================================
# Public API Routes
# Provides REST API endpoints for external/AJAX access
# ============================================================

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime, date
from app.factory import db
from app.models import Department, Doctor, Appointment
from app.ai_scheduler import scheduler

api_bp = Blueprint('api', __name__)


@api_bp.route('/health')
def health_check():
    """API health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'AI Hospital Appointment Scheduler',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat()
    })


@api_bp.route('/departments')
def get_departments():
    """Public: Get all active departments."""
    departments = Department.query.filter_by(is_active=True).all()
    return jsonify({
        'success': True,
        'departments': [d.to_dict() for d in departments]
    })


@api_bp.route('/doctors')
def get_doctors():
    """Public: Get all doctors (optionally filter by department)."""
    dept_id = request.args.get('department_id')
    
    query = Doctor.query
    if dept_id:
        query = query.filter_by(department_id=int(dept_id))
    
    doctors = query.all()
    active = [d for d in doctors if d.user.is_active]
    
    return jsonify({
        'success': True,
        'doctors': [d.to_dict() for d in active]
    })


@api_bp.route('/slots')
def get_slots():
    """
    Public: Get available appointment slots.
    
    Query params:
        - department_id (required)
        - date (required, YYYY-MM-DD)
        - doctor_id (optional)
    """
    dept_id = request.args.get('department_id')
    date_str = request.args.get('date')
    doctor_id = request.args.get('doctor_id')
    
    if not dept_id or not date_str:
        return jsonify({'success': False, 'error': 'department_id and date are required'}), 400
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date format'}), 400
    
    slots = scheduler.get_available_slots_for_date(
        int(dept_id),
        target_date,
        int(doctor_id) if doctor_id else None
    )
    
    return jsonify({
        'success': True,
        'slots': slots,
        'total': len(slots)
    })


@api_bp.route('/predict-wait')
@login_required
def predict_wait_time():
    """
    Predict waiting time for a potential appointment.
    
    Query params:
        - doctor_id, date, time
    """
    doctor_id = request.args.get('doctor_id')
    date_str = request.args.get('date')
    time_str = request.args.get('time')
    
    if not all([doctor_id, date_str, time_str]):
        return jsonify({'success': False, 'error': 'doctor_id, date, and time are required'}), 400
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        target_time = datetime.strptime(time_str, '%H:%M').time()
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date/time format'}), 400
    
    doctor = Doctor.query.get(int(doctor_id))
    if not doctor:
        return jsonify({'success': False, 'error': 'Doctor not found'}), 404
    
    estimated = scheduler.predict_waiting_time(
        int(doctor_id), doctor.department_id, target_date, target_time
    )
    
    return jsonify({
        'success': True,
        'estimated_wait_minutes': estimated,
        'doctor': doctor.full_name,
        'date': date_str,
        'time': time_str
    })
