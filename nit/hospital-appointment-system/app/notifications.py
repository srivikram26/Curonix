"""
Notification Simulation Module
===============================
Simulates email/SMS notifications for the hospital appointment system.
In production, these would integrate with actual email (SendGrid, SES) and SMS (Twilio) services.
For this capstone project, notifications are stored in the database and logged to console.
"""

from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_CONFIRMED = "appointment_confirmed"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
    APPOINTMENT_REMINDER = "appointment_reminder"
    APPOINTMENT_COMPLETED = "appointment_completed"
    EMERGENCY_ALERT = "emergency_alert"
    DOCTOR_LEAVE = "doctor_leave"
    SYSTEM_ALERT = "system_alert"


# ── Notification Templates ──────────────────────────────────────────────

TEMPLATES = {
    NotificationType.APPOINTMENT_BOOKED: {
        "patient": {
            "title": "Appointment Confirmed",
            "message": "Your appointment with Dr. {doctor_name} is scheduled for {date} at {time}. "
                       "Department: {department}. AI Priority Score: {priority_score}."
        },
        "doctor": {
            "title": "New Appointment",
            "message": "New appointment scheduled with patient {patient_name} on {date} at {time}. "
                       "Type: {appointment_type}. Priority: {priority}."
        }
    },
    NotificationType.APPOINTMENT_CANCELLED: {
        "patient": {
            "title": "Appointment Cancelled",
            "message": "Your appointment on {date} at {time} with Dr. {doctor_name} has been cancelled."
        },
        "doctor": {
            "title": "Appointment Cancelled",
            "message": "Appointment with {patient_name} on {date} at {time} has been cancelled by the patient."
        }
    },
    NotificationType.APPOINTMENT_RESCHEDULED: {
        "patient": {
            "title": "Appointment Rescheduled",
            "message": "Your appointment has been rescheduled to {date} at {time} with Dr. {doctor_name}."
        },
        "doctor": {
            "title": "Appointment Rescheduled",
            "message": "Appointment with {patient_name} rescheduled to {date} at {time}."
        }
    },
    NotificationType.APPOINTMENT_REMINDER: {
        "patient": {
            "title": "Appointment Reminder",
            "message": "Reminder: You have an appointment tomorrow ({date}) at {time} with Dr. {doctor_name}. "
                       "Please arrive 10 minutes early."
        },
        "doctor": {
            "title": "Tomorrow's Schedule Reminder",
            "message": "Reminder: You have {count} appointments scheduled for tomorrow ({date})."
        }
    },
    NotificationType.APPOINTMENT_CONFIRMED: {
        "patient": {
            "title": "Appointment Confirmed by Doctor",
            "message": "Dr. {doctor_name} has confirmed your appointment on {date} at {time}."
        }
    },
    NotificationType.APPOINTMENT_COMPLETED: {
        "patient": {
            "title": "Appointment Completed",
            "message": "Your appointment with Dr. {doctor_name} on {date} has been marked as completed. "
                       "Thank you for visiting!"
        }
    },
    NotificationType.EMERGENCY_ALERT: {
        "doctor": {
            "title": "⚠️ Emergency Appointment",
            "message": "URGENT: Emergency appointment scheduled for patient {patient_name} on {date} at {time}. "
                       "Priority: Emergency. Please prepare immediately."
        },
        "admin": {
            "title": "Emergency Appointment Alert",
            "message": "Emergency appointment created: Patient {patient_name} with Dr. {doctor_name} on {date} at {time}."
        }
    },
    NotificationType.DOCTOR_LEAVE: {
        "admin": {
            "title": "Doctor Leave Request",
            "message": "Dr. {doctor_name} has requested leave on {date}. Reason: {reason}. "
                       "Affected appointments may need rescheduling."
        }
    },
    NotificationType.SYSTEM_ALERT: {
        "admin": {
            "title": "System Alert",
            "message": "{message}"
        }
    }
}


class NotificationService:
    """
    Simulates a notification delivery system.
    Stores notifications in the database and logs them to indicate
    where real email/SMS integration would occur.
    """

    def __init__(self, app=None):
        self.app = app

    def init_app(self, app):
        self.app = app

    def send(self, notification_type, recipient_id, context=None, channels=None):
        """
        Send a notification to a user.
        
        Args:
            notification_type: NotificationType enum
            recipient_id: User ID of the recipient
            context: Dict with template variables (doctor_name, date, time, etc.)
            channels: List of channels ['in_app', 'email', 'sms'] (default: in_app only)
        
        Returns:
            dict with notification details
        """
        from app.models import Notification, db

        context = context or {}
        channels = channels or ['in_app']

        # Determine recipient role template
        role = context.get('recipient_role', 'patient')
        template = TEMPLATES.get(notification_type, {}).get(role)

        if not template:
            logger.warning(f"No template for {notification_type.value} / {role}")
            template = {"title": "Notification", "message": str(context)}

        # Format message
        title = template["title"]
        try:
            message = template["message"].format(**context)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}")
            message = template["message"]

        # Store in database (in-app notification)
        notification = Notification(
            user_id=recipient_id,
            subject=title,
            message=message,
            type=notification_type.value,
            is_read=False,
            sent_at=datetime.utcnow()
        )
        db.session.add(notification)

        # Simulate email delivery
        if 'email' in channels:
            self._simulate_email(recipient_id, title, message)

        # Simulate SMS delivery
        if 'sms' in channels:
            self._simulate_sms(recipient_id, title, message)

        try:
            db.session.commit()
            logger.info(f"📧 Notification sent: [{notification_type.value}] to user {recipient_id} — {title}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to save notification: {e}")
            return {"success": False, "error": str(e)}

        return {
            "success": True,
            "notification_id": notification.id,
            "title": title,
            "message": message,
            "channels": channels
        }

    def send_appointment_notification(self, notification_type, appointment, extra_context=None):
        """
        Convenience method for appointment-related notifications.
        Automatically extracts context from the appointment object.
        """
        from app.models import User, Doctor

        context = {
            "date": str(appointment.appointment_date),
            "time": str(appointment.start_time) if appointment.start_time else "TBD",
            "appointment_type": appointment.appointment_type or "new",
            "priority": appointment.priority or "normal",
            "priority_score": appointment.priority_score or 0,
        }

        # Get patient info
        patient = User.query.get(appointment.patient_id)
        if patient:
            context["patient_name"] = patient.full_name

        # Get doctor info
        if appointment.doctor_id:
            doctor = Doctor.query.get(appointment.doctor_id)
            if doctor and doctor.user:
                context["doctor_name"] = doctor.user.full_name
                context["department"] = doctor.department.name if doctor.department else "General"

        if extra_context:
            context.update(extra_context)

        results = []

        # Notify patient
        if patient:
            context["recipient_role"] = "patient"
            result = self.send(notification_type, patient.id, context)
            results.append(("patient", result))

        # Notify doctor
        if appointment.doctor_id:
            doctor = Doctor.query.get(appointment.doctor_id)
            if doctor:
                context["recipient_role"] = "doctor"
                result = self.send(notification_type, doctor.user_id, context)
                results.append(("doctor", result))

        # For emergencies, also notify admins
        if notification_type == NotificationType.EMERGENCY_ALERT:
            admins = User.query.filter_by(role='admin', is_active=True).all()
            context["recipient_role"] = "admin"
            for admin in admins:
                result = self.send(notification_type, admin.id, context)
                results.append(("admin", result))

        return results

    def send_bulk_reminders(self):
        """
        Send appointment reminders for tomorrow's appointments.
        Called by a scheduler job (or manually by admin).
        """
        from app.models import Appointment, Doctor, User, db
        from datetime import date, timedelta

        tomorrow = date.today() + timedelta(days=1)
        appointments = Appointment.query.filter(
            Appointment.appointment_date == tomorrow,
            Appointment.status.in_(['scheduled', 'confirmed'])
        ).all()

        count = 0
        for appt in appointments:
            self.send_appointment_notification(NotificationType.APPOINTMENT_REMINDER, appt)
            count += 1

        # Send summary to doctors
        doctor_appt_counts = {}
        for appt in appointments:
            if appt.doctor_id:
                doctor_appt_counts[appt.doctor_id] = doctor_appt_counts.get(appt.doctor_id, 0) + 1

        for doctor_id, appt_count in doctor_appt_counts.items():
            doctor = Doctor.query.get(doctor_id)
            if doctor:
                self.send(NotificationType.APPOINTMENT_REMINDER, doctor.user_id, {
                    "recipient_role": "doctor",
                    "date": str(tomorrow),
                    "count": appt_count
                })

        logger.info(f"📧 Sent {count} appointment reminders for {tomorrow}")
        return {"reminders_sent": count, "date": str(tomorrow)}

    def _simulate_email(self, user_id, subject, body):
        """Simulate email sending — logs to console."""
        logger.info(
            f"📨 [EMAIL SIMULATION] To: User #{user_id}\n"
            f"   Subject: {subject}\n"
            f"   Body: {body[:100]}..."
        )

    def _simulate_sms(self, user_id, subject, body):
        """Simulate SMS sending — logs to console."""
        logger.info(
            f"📱 [SMS SIMULATION] To: User #{user_id}\n"
            f"   Message: {subject} - {body[:80]}..."
        )

    def get_unread_count(self, user_id):
        """Get count of unread notifications for a user."""
        from app.models import Notification
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()

    def mark_as_read(self, notification_id, user_id):
        """Mark a notification as read."""
        from app.models import Notification, db
        notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if notif:
            notif.is_read = True
            db.session.commit()
            return True
        return False

    def mark_all_read(self, user_id):
        """Mark all notifications as read for a user."""
        from app.models import Notification, db
        Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
        db.session.commit()


# Global instance
notification_service = NotificationService()
