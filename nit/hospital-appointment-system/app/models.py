# ============================================================
# SQLAlchemy Database Models
# Defines all ORM models mapping to MySQL tables
# ============================================================

from datetime import datetime, date, time
from app.factory import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# User Loader for Flask-Login
# ============================================================
@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login session management."""
    return User.query.get(int(user_id))


# ============================================================
# MODEL: Department
# Represents hospital departments
# ============================================================
class Department(db.Model):
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    floor_number = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    doctors = db.relationship('Doctor', backref='department', lazy='dynamic')
    appointments = db.relationship('Appointment', backref='department', lazy='dynamic')
    
    def to_dict(self):
        """Serialize department to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'floor_number': self.floor_number,
            'is_active': self.is_active,
            'doctor_count': self.doctors.count()
        }
    
    def __repr__(self):
        return f'<Department {self.name}>'


# ============================================================
# MODEL: User
# Base user model with role-based access (patient/doctor/admin)
# ============================================================
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum('patient', 'doctor', 'admin'), nullable=False, default='patient')
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.Enum('male', 'female', 'other'))
    blood_group = db.Column(db.String(5))
    address = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    is_senior_citizen = db.Column(db.Boolean, default=False)
    profile_image = db.Column(db.String(255))
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    doctor_profile = db.relationship('Doctor', backref='user', uselist=False, lazy='joined')
    patient_appointments = db.relationship(
        'Appointment', backref='patient', lazy='dynamic',
        foreign_keys='Appointment.patient_id'
    )
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        """Hash and store the user's password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        """Return user's full name."""
        return f"{self.first_name} {self.last_name}"
    
    def calculate_senior_citizen(self):
        """Auto-detect senior citizen status based on age (60+)."""
        if self.date_of_birth:
            today = date.today()
            age = today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
            self.is_senior_citizen = age >= 60

    @property
    def age(self):
        """Return the current age in years if DOB is known."""
        if not self.date_of_birth:
            return None
        today = date.today()
        age = today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
        return max(age, 0)
    
    def to_dict(self):
        """Serialize user to dictionary (excludes password)."""
        return {
            'id': self.id,
            'email': self.email,
            'role': self.role,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'phone': self.phone,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'gender': self.gender,
            'blood_group': self.blood_group,
            'age': self.age,
            'address': self.address,
            'is_active': self.is_active,
            'is_senior_citizen': self.is_senior_citizen
        }
    
    def __repr__(self):
        return f'<User {self.email} ({self.role})>'


# ============================================================
# MODEL: Doctor
# Extended doctor profile linked to User
# ============================================================
class Doctor(db.Model):
    __tablename__ = 'doctors'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    specialization = db.Column(db.String(200))
    qualification = db.Column(db.String(300))
    experience_years = db.Column(db.Integer, default=0)
    consultation_fee = db.Column(db.Numeric(10, 2), default=0.00)
    max_patients_per_day = db.Column(db.Integer, default=20)
    avg_consultation_time = db.Column(db.Integer, default=30)  # minutes
    rating = db.Column(db.Numeric(3, 2), default=0.00)
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    availability = db.relationship('DoctorAvailability', backref='doctor', lazy='dynamic')
    leaves = db.relationship('DoctorLeave', backref='doctor', lazy='dynamic')
    appointments = db.relationship('Appointment', backref='doctor', lazy='dynamic')
    waiting_logs = db.relationship('WaitingTimeLog', backref='doctor', lazy='dynamic')
    
    @property
    def full_name(self):
        return f"Dr. {self.user.first_name} {self.user.last_name}"
    
    def get_daily_appointment_count(self, target_date):
        """Count appointments for a specific date."""
        return self.appointments.filter(
            Appointment.appointment_date == target_date,
            Appointment.status.in_(['scheduled', 'confirmed', 'in_progress'])
        ).count()
    
    def get_workload_ratio(self, target_date):
        """Calculate workload ratio (0.0 to 1.0) for load balancing."""
        current = self.get_daily_appointment_count(target_date)
        return current / self.max_patients_per_day if self.max_patients_per_day > 0 else 1.0
    
    def is_on_leave(self, target_date):
        """Check if doctor is on leave on a given date."""
        return self.leaves.filter_by(leave_date=target_date).first() is not None
    
    def to_dict(self):
        """Serialize doctor to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.full_name,
            'email': self.user.email,
            'address': self.user.address,
            'department': self.department.name if self.department else None,
            'department_id': self.department_id,
            'specialization': self.specialization,
            'qualification': self.qualification,
            'experience_years': self.experience_years,
            'consultation_fee': float(self.consultation_fee) if self.consultation_fee else 0,
            'max_patients_per_day': self.max_patients_per_day,
            'avg_consultation_time': self.avg_consultation_time,
            'rating': float(self.rating) if self.rating else 0,
            'bio': self.bio,
            'is_active': self.user.is_active,
            'status_display': 'Active' if self.user.is_active else 'Deactivated'
        }
    
    def __repr__(self):
        return f'<Doctor {self.full_name}>'


# ============================================================
# MODEL: DoctorAvailability
# Weekly schedule slots for each doctor
# ============================================================
class DoctorAvailability(db.Model):
    __tablename__ = 'doctor_availability'
    
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    day_of_week = db.Column(db.SmallInteger, nullable=False)  # 0=Monday, 6=Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    max_slots = db.Column(db.Integer, default=16)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    @property
    def day_name(self):
        return self.DAY_NAMES[self.day_of_week] if 0 <= self.day_of_week <= 6 else 'Unknown'
    
    def to_dict(self):
        return {
            'id': self.id,
            'doctor_id': self.doctor_id,
            'day_of_week': self.day_of_week,
            'day_name': self.day_name,
            'start_time': self.start_time.strftime('%H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'is_available': self.is_available,
            'max_slots': self.max_slots
        }


# ============================================================
# MODEL: DoctorLeave
# Individual leave dates for doctors
# ============================================================
class DoctorLeave(db.Model):
    __tablename__ = 'doctor_leaves'
    
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    leave_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'doctor_id': self.doctor_id,
            'leave_date': self.leave_date.isoformat(),
            'reason': self.reason
        }


# ============================================================
# MODEL: Appointment
# Core appointment data with AI scheduling metadata
# ============================================================
class Appointment(db.Model):
    __tablename__ = 'appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    location = db.Column(db.String(150))
    appointment_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(
        db.Enum('scheduled', 'confirmed', 'in_progress', 'completed',
                'cancelled', 'no_show', 'rescheduled'),
        default='scheduled'
    )
    priority = db.Column(
        db.Enum('emergency', 'senior_citizen', 'follow_up', 'normal'),
        default='normal'
    )
    priority_score = db.Column(db.Integer, default=10)
    appointment_type = db.Column(
        db.Enum('new', 'follow_up', 'emergency'), default='new'
    )
    symptoms = db.Column(db.Text)
    notes = db.Column(db.Text)
    ai_scheduled = db.Column(db.Boolean, default=False)
    estimated_wait_time = db.Column(db.Integer, default=0)
    actual_wait_time = db.Column(db.Integer)
    cancellation_reason = db.Column(db.Text)
    rescheduled_from = db.Column(db.Integer, db.ForeignKey('appointments.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    history = db.relationship('AppointmentHistory', backref='appointment', lazy='dynamic')
    
    def to_dict(self):
        """Serialize appointment to dictionary."""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': self.patient.full_name if self.patient else None,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor.full_name if self.doctor else None,
            'department': self.department.name if self.department else None,
            'department_id': self.department_id,
            'location': self.location,
            'appointment_date': self.appointment_date.isoformat() if self.appointment_date else None,
            'start_time': self.start_time.strftime('%H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'status': self.status,
            'priority': self.priority,
            'priority_score': self.priority_score,
            'appointment_type': self.appointment_type,
            'symptoms': self.symptoms,
            'notes': self.notes,
            'ai_scheduled': self.ai_scheduled,
            'estimated_wait_time': self.estimated_wait_time,
            'actual_wait_time': self.actual_wait_time,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Appointment {self.id} - {self.status}>'


# ============================================================
# MODEL: AppointmentHistory
# Audit trail for appointment modifications
# ============================================================
class AppointmentHistory(db.Model):
    __tablename__ = 'appointment_history'
    
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    old_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50))
    old_date = db.Column(db.Date)
    new_date = db.Column(db.Date)
    old_time = db.Column(db.Time)
    new_time = db.Column(db.Time)
    change_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'appointment_id': self.appointment_id,
            'changed_by': self.changed_by,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'old_date': self.old_date.isoformat() if self.old_date else None,
            'new_date': self.new_date.isoformat() if self.new_date else None,
            'change_reason': self.change_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================================
# MODEL: WaitingTimeLog
# Historical data used by AI to predict waiting times
# ============================================================
class WaitingTimeLog(db.Model):
    __tablename__ = 'waiting_time_log'
    
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.Time, nullable=False)
    day_of_week = db.Column(db.SmallInteger, nullable=False)
    hour_of_day = db.Column(db.SmallInteger, nullable=False)
    scheduled_patients = db.Column(db.Integer, default=0)
    actual_wait_minutes = db.Column(db.Integer, default=0)
    is_peak_hour = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================================
# MODEL: Notification
# SMS/Email notification simulation records
# ============================================================
class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'))
    type = db.Column(db.Enum('email', 'sms', 'system'), default='system')
    subject = db.Column(db.String(255))
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'subject': self.subject,
            'message': self.message,
            'is_read': self.is_read,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None
        }


# ============================================================
# MODEL: SystemSetting
# Configurable system parameters
# ============================================================
class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get_setting(key, default=None):
        """Retrieve a system setting by key."""
        setting = SystemSetting.query.filter_by(setting_key=key).first()
        return setting.setting_value if setting else default
