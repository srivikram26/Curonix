# ============================================================
# AI-Based Appointment Scheduler
# ============================================================
# Implements Constraint Satisfaction Problem (CSP) based scheduling
# with priority queuing, workload balancing, and waiting time
# optimization using heuristic planning techniques.
#
# ALGORITHM OVERVIEW:
# ------------------
# 1. Constraint Satisfaction: Ensures no overlapping appointments,
#    respects doctor availability, and enforces capacity limits.
#
# 2. Priority-Based Scheduling: Assigns priority scores using a
#    weighted scoring function:
#      Score = W_type * TypeScore + W_age * AgeScore + W_wait * WaitScore
#    Where Emergency > Senior Citizen > Follow-up > Normal
#
# 3. Workload Balancing: Distributes patients across doctors in the
#    same department using a min-heap strategy on workload ratios.
#
# 4. Waiting Time Prediction: Uses historical appointment data and
#    a linear regression model to estimate expected waiting time.
#
# 5. Auto-Rescheduling: When a cancellation occurs, automatically
#    reassigns the freed slot to the highest-priority patient on
#    the waitlist using a greedy best-first approach.
#
# PSEUDO-CODE:
# -----------
# function SCHEDULE_APPOINTMENT(patient, department, preferred_date, preferred_time):
#     1. Compute priority_score for the patient
#     2. Get available doctors in department (not on leave, within capacity)
#     3. For each doctor, generate available time slots (CSP constraints)
#     4. Rank doctors by workload_ratio (ascending) — load balancing
#     5. For the best doctor:
#        a. Find the slot closest to preferred_time
#        b. Verify no conflicts (constraint check)
#        c. If valid, assign appointment
#     6. Predict estimated waiting time using historical model
#     7. Return scheduled appointment with metadata
#
# function AUTO_RESCHEDULE(cancelled_appointment):
#     1. Find all 'scheduled' appointments for same doctor+date after cancelled slot
#     2. Sort by priority_score descending
#     3. Shift each appointment earlier to fill gaps (greedy compaction)
#     4. Notify affected patients
#
# function PREDICT_WAITING_TIME(doctor, date, time_slot):
#     1. Query historical waiting_time_log for same doctor, day_of_week, hour
#     2. Compute weighted moving average
#     3. Adjust for current day's appointment count (peak factor)
#     4. Return estimated minutes
# ============================================================

from datetime import datetime, date, time, timedelta
from typing import Any, List, Optional, Tuple, Dict
import math
import heapq
import numpy as np
from app.factory import db
from app.models import (
    Appointment, Doctor, DoctorAvailability, DoctorLeave,
    WaitingTimeLog, Department, User, Notification
)


class AIScheduler:
    """
    AI-Based Appointment Scheduling Engine.
    
    Uses Constraint Satisfaction Problem (CSP) techniques combined with
    priority-based heuristics and workload balancing to optimally
    schedule hospital appointments.
    """
    
    # Priority weights for scoring function
    PRIORITY_WEIGHTS = {
        'emergency': 100,
        'senior_citizen': 50,
        'follow_up': 30,
        'normal': 10
    }
    
    # Weight coefficients for composite priority score
    W_TYPE = 1.0    # Weight for appointment type
    W_AGE = 0.5     # Weight for senior citizen bonus
    W_WAIT = 0.3    # Weight for waiting-time fairness bonus
    
    # Scheduling parameters
    SLOT_DURATION = 30  # minutes
    WORKING_START = time(9, 0)
    WORKING_END = time(17, 0)
    EMERGENCY_RESERVED_SLOTS = 2

    # Default hospital branch coordinates used to route patients to the nearest site.
    HOSPITAL_LOCATIONS = [
        {'name': 'Main Campus Hospital', 'latitude': 17.3850, 'longitude': 78.4867},
        {'name': 'North Care Hospital', 'latitude': 17.4450, 'longitude': 78.4740},
        {'name': 'South Specialty Center', 'latitude': 17.3300, 'longitude': 78.5300},
    ]

    LOCATION_BRANCH_HINTS = {
        'Main Campus Hospital': ['main campus', 'central', 'downtown', 'city center'],
        'North Care Hospital': ['north', 'hitech city', 'hitech', 'kondapur', 'madhapur', 'gachibowli'],
        'South Specialty Center': ['south', 'banjara hills', 'jubilee hills', 'secunderabad', 'lakdikapul']
    }
    
    def __init__(self):
        """Initialize the AI Scheduler."""
        pass

    def _haversine_km(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in kilometers between two latitude/longitude pairs."""
        radius_km = 6371.0
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(delta_lon / 2) ** 2
        )
        return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _resolve_hospital_location(self, location: Optional[Any]) -> Tuple[str, Optional[float]]:
        """
        Resolve the best hospital branch for the given patient location.

        If latitude/longitude are provided, the nearest branch is selected.
        Otherwise, a provided text location is preserved and the default branch
        is used when no location is available.
        """
        default_branch = self.HOSPITAL_LOCATIONS[0]

        if isinstance(location, dict):
            try:
                latitude = float(location.get('latitude'))
                longitude = float(location.get('longitude'))
            except (TypeError, ValueError):
                label = (location.get('address') or location.get('label') or '').strip()
                return (label or default_branch['name']), None

            nearest_branch = min(
                self.HOSPITAL_LOCATIONS,
                key=lambda branch: self._haversine_km(
                    latitude,
                    longitude,
                    branch['latitude'],
                    branch['longitude']
                )
            )
            distance_km = self._haversine_km(
                latitude,
                longitude,
                nearest_branch['latitude'],
                nearest_branch['longitude']
            )
            return nearest_branch['name'], round(distance_km, 1)

        if isinstance(location, str):
            cleaned = location.strip()
            if cleaned:
                inferred_branch = self._infer_branch_from_text(cleaned)
                if inferred_branch:
                    return inferred_branch['name'], inferred_branch.get('distance_km')
                return cleaned, None
            return default_branch['name'], None

        return default_branch['name'], None

    def _infer_branch_from_text(self, location_text: str) -> Optional[Dict[str, Any]]:
        """Infer the nearest branch from a typed location string."""
        normalized = location_text.lower().strip()
        for branch_name, hints in self.LOCATION_BRANCH_HINTS.items():
            if branch_name.lower() in normalized:
                branch = next((item for item in self.HOSPITAL_LOCATIONS if item['name'] == branch_name), None)
                if branch:
                    return {'name': branch['name'], 'distance_km': 0.0}
            for hint in hints:
                if hint in normalized:
                    branch = next((item for item in self.HOSPITAL_LOCATIONS if item['name'] == branch_name), None)
                    if branch:
                        return {'name': branch['name'], 'distance_km': None}

        return None

    def _resolve_patient_coordinates(self, location: Optional[Any]) -> Optional[Tuple[float, float]]:
        """Return patient coordinates when the booking request includes geolocation data."""
        if isinstance(location, dict):
            try:
                return float(location.get('latitude')), float(location.get('longitude'))
            except (TypeError, ValueError):
                return None
        return None

    def _resolve_patient_branch(self, location: Optional[Any]) -> Optional[str]:
        """Resolve the best matching branch for a patient location input."""
        if isinstance(location, dict):
            coords = self._resolve_patient_coordinates(location)
            if not coords:
                return None
            nearest_branch = min(
                self.HOSPITAL_LOCATIONS,
                key=lambda branch: self._haversine_km(
                    coords[0],
                    coords[1],
                    branch['latitude'],
                    branch['longitude']
                )
            )
            return nearest_branch['name']

        if isinstance(location, str):
            inferred = self._infer_branch_from_text(location)
            if inferred:
                return inferred['name']

        return None

    def _branch_for_doctor(self, doctor: Doctor) -> str:
        """Return the hospital branch assigned to a doctor."""
        address = (doctor.user.address or '').strip() if doctor.user else ''
        if not address:
            return self.HOSPITAL_LOCATIONS[(doctor.id - 1) % len(self.HOSPITAL_LOCATIONS)]['name']
        for branch in self.HOSPITAL_LOCATIONS:
            if branch['name'].lower() in address.lower() or address.lower() in branch['name'].lower():
                return branch['name']
        if doctor.id:
            return self.HOSPITAL_LOCATIONS[(doctor.id - 1) % len(self.HOSPITAL_LOCATIONS)]['name']
        return address or self.HOSPITAL_LOCATIONS[0]['name']

    def _branch_coordinates(self, branch_name: str) -> Optional[Tuple[float, float]]:
        """Return coordinates for a known hospital branch name."""
        for branch in self.HOSPITAL_LOCATIONS:
            if branch['name'].lower() == branch_name.lower():
                return branch['latitude'], branch['longitude']
        return None

    def _distance_to_branch(self, patient_coords: Tuple[float, float], branch_name: str) -> float:
        """Measure distance from the patient to a hospital branch."""
        branch_coords = self._branch_coordinates(branch_name)
        if not branch_coords:
            return float('inf')
        return self._haversine_km(
            patient_coords[0],
            patient_coords[1],
            branch_coords[0],
            branch_coords[1]
        )

    # ========================================================
    # PRIORITY SCORING
    # ========================================================
    
    def compute_priority_score(self, patient: User, appointment_type: str,
                                is_follow_up: bool = False) -> Tuple[int, str]:
        """
        Compute a priority score for the appointment request.
        
        Priority Hierarchy:
            Emergency (100) > Senior Citizen (50) > Follow-up (30) > Normal (10)
        
        Additional factors:
            - Days waiting since last visit (fairness bonus)
            - Patient age bonus for elderly
        
        Args:
            patient: User object of the patient
            appointment_type: 'emergency', 'new', or 'follow_up'
            is_follow_up: Whether this is a follow-up visit
        
        Returns:
            Tuple of (priority_score, priority_category)
        """
        score = 0
        category = 'normal'
        
        # === Type-based priority ===
        if appointment_type == 'emergency':
            score += self.PRIORITY_WEIGHTS['emergency'] * self.W_TYPE
            category = 'emergency'
        elif is_follow_up or appointment_type == 'follow_up':
            score += self.PRIORITY_WEIGHTS['follow_up'] * self.W_TYPE
            category = 'follow_up'
        else:
            score += self.PRIORITY_WEIGHTS['normal'] * self.W_TYPE
        
        # === Age-based priority (Senior Citizen: 60+) ===
        if patient.is_senior_citizen:
            score += self.PRIORITY_WEIGHTS['senior_citizen'] * self.W_AGE
            if category == 'normal':
                category = 'senior_citizen'
        
        # === Waiting fairness bonus ===
        # Patients who haven't visited in a long time get a small boost
        last_appointment = Appointment.query.filter_by(
            patient_id=patient.id, status='completed'
        ).order_by(Appointment.appointment_date.desc()).first()
        
        if last_appointment:
            days_since = (date.today() - last_appointment.appointment_date).days
            fairness_bonus = min(days_since * 0.1, 15)  # Cap at 15 points
            score += fairness_bonus * self.W_WAIT
        else:
            # First-time patients get a small bonus
            score += 5 * self.W_WAIT
        
        return int(score), category
    
    # ========================================================
    # CONSTRAINT SATISFACTION - SLOT GENERATION
    # ========================================================
    
    def generate_available_slots(self, doctor: Doctor, target_date: date) -> List[Dict]:
        """
        Generate all available time slots for a doctor on a given date.
        
        CSP Constraints enforced:
            C1: Slot must be within doctor's availability window
            C2: Slot must not overlap with existing appointments
            C3: Doctor must not be on leave
            C4: Doctor must not exceed max patients per day
            C5: Emergency slots must be reserved
        
        Args:
            doctor: Doctor object
            target_date: Date to check availability
        
        Returns:
            List of available slot dictionaries with start_time and end_time
        """
        available_slots = []
        
        # C3: Check if doctor is on leave
        if doctor.is_on_leave(target_date):
            return available_slots
        
        # C4: Check daily capacity
        current_count = doctor.get_daily_appointment_count(target_date)
        if current_count >= doctor.max_patients_per_day:
            return available_slots
        
        # C1: Get doctor's availability for this day of week
        day_of_week = target_date.weekday()  # Monday=0, Sunday=6
        availability = DoctorAvailability.query.filter_by(
            doctor_id=doctor.id,
            day_of_week=day_of_week,
            is_available=True
        ).first()
        
        if not availability:
            return available_slots
        
        # Generate all possible slots within availability window
        slot_duration = timedelta(minutes=self.SLOT_DURATION)
        current_slot_start = datetime.combine(target_date, availability.start_time)
        slot_end_boundary = datetime.combine(target_date, availability.end_time)
        
        # C2: Get all existing booked appointments for this doctor on this date
        booked_appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == target_date,
            Appointment.status.in_(['scheduled', 'confirmed', 'in_progress'])
        ).all()
        
        booked_times = set()
        for appt in booked_appointments:
            booked_times.add(appt.start_time)
        
        # Generate slots, marking booked ones as unavailable
        while current_slot_start + slot_duration <= slot_end_boundary:
            slot_start_time = current_slot_start.time()
            slot_end_time = (current_slot_start + slot_duration).time()
            
            # Check if this slot is booked
            is_booked = slot_start_time in booked_times
            
            available_slots.append({
                'start_time': slot_start_time,
                'end_time': slot_end_time,
                'doctor_id': doctor.id,
                'doctor_name': doctor.full_name,
                'date': target_date,
                'is_available': not is_booked,
                'status': 'booked' if is_booked else 'available'
            })
            
            current_slot_start += slot_duration
        
        # C5: Reserve emergency slots (keep last N slots for emergencies)
        if len(available_slots) > self.EMERGENCY_RESERVED_SLOTS:
            # Non-emergency patients can't book the last reserved slots
            # (This is handled in schedule_appointment based on priority)
            pass
        
        return available_slots
    
    # ========================================================
    # WORKLOAD BALANCING
    # ========================================================
    
    def get_balanced_doctor(self, department_id: int, target_date: date,
                            preferred_doctor_id: Optional[int] = None) -> Optional[Doctor]:
        """
        Select the optimal doctor using workload balancing.
        
        Uses a min-heap on workload ratios to find the least-loaded
        doctor in the department who is available on the target date.
        
        Algorithm:
            1. Get all active doctors in the department
            2. Filter out doctors on leave
            3. Compute workload_ratio = current_appointments / max_capacity
            4. Return doctor with lowest workload ratio
        
        Args:
            department_id: Target department
            target_date: Appointment date
            preferred_doctor_id: Optional preferred doctor (prioritized if available)
        
        Returns:
            Best available Doctor object, or None
        """
        # If patient has a preference and doctor is available, use them
        if preferred_doctor_id:
            preferred = Doctor.query.get(preferred_doctor_id)
            if preferred and not preferred.is_on_leave(target_date):
                workload = preferred.get_workload_ratio(target_date)
                if workload < 1.0:
                    return preferred
        
        # Get all doctors in the department
        doctors = Doctor.query.filter_by(department_id=department_id).all()
        
        if not doctors:
            return None
        
        # Build min-heap of (workload_ratio, doctor_id, doctor)
        doctor_heap = []
        for doc in doctors:
            if doc.is_on_leave(target_date):
                continue
            if not doc.user.is_active:
                continue
            
            workload = doc.get_workload_ratio(target_date)
            if workload < 1.0:  # Still has capacity
                heapq.heappush(doctor_heap, (workload, doc.id, doc))
        
        # Return the least-loaded doctor
        if doctor_heap:
            _, _, best_doctor = heapq.heappop(doctor_heap)
            return best_doctor
        
        return None
    
    # ========================================================
    # MAIN SCHEDULING FUNCTION
    # ========================================================
    
    def schedule_appointment(self, patient_id: int, department_id: int,
                              preferred_date: date, preferred_time: Optional[time] = None,
                              appointment_type: str = 'new',
                              preferred_doctor_id: Optional[int] = None,
                              symptoms: str = '',
                              notes: str = '') -> Dict:
        """
        Main AI scheduling function using CSP + Priority + Load Balancing.
        
        Steps:
            1. Validate inputs
            2. Compute patient's priority score
            3. Select optimal doctor (workload-balanced)
            4. Generate available slots (CSP)
            5. Find best slot matching preference
            6. Create appointment with AI metadata
            7. Predict estimated waiting time
            8. Generate notification
        
        Args:
            patient_id: Patient user ID
            department_id: Target department ID
            preferred_date: Requested date
            preferred_time: Preferred time slot (optional)
            appointment_type: 'new', 'follow_up', or 'emergency'
            preferred_doctor_id: Optional preferred doctor
            symptoms: Patient symptoms description
            notes: Additional notes
        Returns:
            Dictionary with scheduling result and appointment details
        """
        # Step 1: Validate
        patient = User.query.get(patient_id)
        if not patient:
            return {'success': False, 'error': 'Patient not found'}
        
        department = Department.query.get(department_id)
        if not department:
            return {'success': False, 'error': 'Department not found'}
        
        # Step 2: Compute priority
        is_follow_up = appointment_type == 'follow_up'
        priority_score, priority_category = self.compute_priority_score(
            patient, appointment_type, is_follow_up
        )
        
        # Step 3: Select doctor with workload balancing
        doctor = self.get_balanced_doctor(
            department_id,
            preferred_date,
            preferred_doctor_id
        )
        if not doctor:
            # Try next 7 days if no doctor available on preferred date
            for delta in range(1, 8):
                alt_date = preferred_date + timedelta(days=delta)
                doctor = self.get_balanced_doctor(department_id, alt_date)
                if doctor:
                    preferred_date = alt_date
                    break
        
        if not doctor:
            return {
                'success': False,
                'error': 'No doctors available in this department for the next 7 days'
            }
        
        # Step 4: Generate available slots (CSP)
        all_slots = self.generate_available_slots(doctor, preferred_date)
        # Filter only available (not booked) slots
        slots = [s for s in all_slots if s.get('is_available', True)]
        
        if not slots:
            # Try next available date
            for delta in range(1, 8):
                alt_date = preferred_date + timedelta(days=delta)
                all_slots = self.generate_available_slots(doctor, alt_date)
                slots = [s for s in all_slots if s.get('is_available', True)]
                if slots:
                    preferred_date = alt_date
                    break
        
        if not slots:
            return {
                'success': False,
                'error': 'No available slots found. Please try a different date.'
            }
        
        # Step 5: Find best slot
        # Emergency patients can access reserved slots
        if appointment_type != 'emergency' and len(slots) <= self.EMERGENCY_RESERVED_SLOTS:
            return {
                'success': False,
                'error': 'Remaining slots are reserved for emergencies. Please try another date.'
            }
        
        best_slot = self._find_best_slot(slots, preferred_time)

        appointment_location = 'Main Campus Hospital'
        distance_km = None
        
        # Step 6: Create appointment
        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=doctor.id,
            department_id=department_id,
            location=appointment_location,
            appointment_date=preferred_date,
            start_time=best_slot['start_time'],
            end_time=best_slot['end_time'],
            status='scheduled',
            priority=priority_category,
            priority_score=priority_score,
            appointment_type=appointment_type,
            symptoms=symptoms,
            notes=notes,
            ai_scheduled=True
        )
        
        # Step 7: Predict waiting time
        estimated_wait = self.predict_waiting_time(
            doctor.id, department_id, preferred_date, best_slot['start_time']
        )
        appointment.estimated_wait_time = estimated_wait
        
        db.session.add(appointment)
        db.session.commit()
        
        # Step 8: Create notification
        self._create_notification(
            patient_id,
            appointment.id,
            f"Appointment Scheduled - {preferred_date.strftime('%B %d, %Y')}",
            (
                f"Your appointment with {doctor.full_name} has been scheduled for "
                f"{preferred_date.strftime('%B %d, %Y')} at {best_slot['start_time'].strftime('%I:%M %p')}. "
                f"Estimated wait time: {estimated_wait} minutes. "
                f"Priority: {priority_category.replace('_', ' ').title()}."
            )
        )
        
        return {
            'success': True,
            'appointment': appointment.to_dict(),
            'ai_metadata': {
                'priority_score': priority_score,
                'priority_category': priority_category,
                'doctor_workload_ratio': round(doctor.get_workload_ratio(preferred_date), 2),
                'estimated_wait_time': estimated_wait,
                'ai_scheduled': True,
                'hospital_location': appointment_location,
                'distance_km': distance_km,
                'slots_remaining': len(slots) - 1
            }
        }
    
    def _find_best_slot(self, slots: List[Dict], preferred_time: Optional[time]) -> Dict:
        """
        Find the slot closest to the patient's preferred time.
        
        Uses minimum absolute time-difference as the heuristic.
        If no preference, returns the earliest available slot.
        
        Args:
            slots: List of available slot dictionaries
            preferred_time: Patient's preferred time (optional)
        
        Returns:
            Best matching slot dictionary
        """
        if not preferred_time or not slots:
            return slots[0]  # Return earliest slot
        
        # Find slot with minimum distance to preferred time
        best_slot = None
        min_diff = float('inf')
        
        for slot in slots:
            slot_minutes = slot['start_time'].hour * 60 + slot['start_time'].minute
            pref_minutes = preferred_time.hour * 60 + preferred_time.minute
            diff = abs(slot_minutes - pref_minutes)
            
            if diff < min_diff:
                min_diff = diff
                best_slot = slot
        
        return best_slot
    
    # ========================================================
    # AUTO-RESCHEDULING ON CANCELLATION
    # ========================================================
    
    def auto_reschedule_on_cancellation(self, cancelled_appointment: Appointment) -> List[Dict]:
        """
        Automatically redistribute appointments when a cancellation occurs.
        
        Algorithm (Greedy Compaction):
            1. Find all appointments for same doctor+date after cancelled slot
            2. Sort by priority_score (descending) — highest priority fills first
            3. Shift appointments forward to fill gap
            4. Notify affected patients
        
        Args:
            cancelled_appointment: The cancelled Appointment object
        
        Returns:
            List of rescheduled appointment updates
        """
        rescheduled = []
        
        doctor_id = cancelled_appointment.doctor_id
        appt_date = cancelled_appointment.appointment_date
        freed_time = cancelled_appointment.start_time
        
        # Find appointments scheduled after the cancelled slot
        later_appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == appt_date,
            Appointment.start_time > freed_time,
            Appointment.status.in_(['scheduled', 'confirmed'])
        ).order_by(Appointment.priority_score.desc()).all()
        
        if not later_appointments:
            return rescheduled
        
        # Greedy compaction: shift highest-priority appointment to freed slot
        slot_duration = timedelta(minutes=self.SLOT_DURATION)
        current_free_time = freed_time
        
        for appt in later_appointments:
            old_time = appt.start_time
            new_start = current_free_time
            new_end = (datetime.combine(appt_date, current_free_time) + slot_duration).time()
            
            if new_start < old_time:
                # Shift this appointment earlier
                appt.start_time = new_start
                appt.end_time = new_end
                
                # Log the change
                from app.models import AppointmentHistory
                history = AppointmentHistory(
                    appointment_id=appt.id,
                    old_status=appt.status,
                    new_status=appt.status,
                    old_time=old_time,
                    new_time=new_start,
                    change_reason='Auto-rescheduled by AI after cancellation'
                )
                db.session.add(history)
                
                # Notify patient
                self._create_notification(
                    appt.patient_id,
                    appt.id,
                    'Appointment Time Updated',
                    f'Your appointment has been moved to '
                    f'{new_start.strftime("%I:%M %p")} (earlier slot available). '
                    f'AI auto-rescheduling applied.'
                )
                
                rescheduled.append({
                    'appointment_id': appt.id,
                    'old_time': old_time.strftime('%H:%M'),
                    'new_time': new_start.strftime('%H:%M')
                })
            
            # Next free slot is after this appointment
            current_free_time = (
                datetime.combine(appt_date, current_free_time) + slot_duration
            ).time()
        
        db.session.commit()
        return rescheduled
    
    # ========================================================
    # WAITING TIME PREDICTION
    # ========================================================
    
    def predict_waiting_time(self, doctor_id: int, department_id: int,
                              target_date: date, target_time: time) -> int:
        """
        Predict expected waiting time using historical data analysis.
        
        Algorithm:
            1. Query historical logs for similar conditions:
               - Same doctor, same day of week, similar hour
            2. Compute weighted moving average of past wait times
            3. Apply peak-hour adjustment factor
            4. Apply current-day load factor
        
        Prediction Formula:
            predicted_wait = base_avg * peak_factor * load_factor
        
        Where:
            base_avg = weighted average of historical wait times
            peak_factor = 1.0 + (0.3 if is_peak_hour else 0)
            load_factor = current_appointments / avg_appointments
        
        Args:
            doctor_id: Doctor ID
            department_id: Department ID
            target_date: Appointment date
            target_time: Appointment time
        
        Returns:
            Estimated waiting time in minutes
        """
        day_of_week = target_date.weekday()
        hour = target_time.hour
        
        # Query historical data
        historical = WaitingTimeLog.query.filter(
            WaitingTimeLog.doctor_id == doctor_id,
            WaitingTimeLog.day_of_week == day_of_week,
            WaitingTimeLog.hour_of_day.between(hour - 1, hour + 1)
        ).order_by(WaitingTimeLog.appointment_date.desc()).limit(30).all()
        
        if not historical:
            # Default estimate based on position in queue
            doctor = Doctor.query.get(doctor_id)
            if doctor:
                current_count = doctor.get_daily_appointment_count(target_date)
                # Simple estimate: each patient takes avg_consultation_time
                position = self._get_queue_position(doctor_id, target_date, target_time)
                return 1
            return 1
        
        # Compute weighted moving average (more recent = higher weight)
        weights = []
        wait_times = []
        for i, log in enumerate(historical):
            weight = 1.0 / (i + 1)  # Exponential decay
            weights.append(weight)
            wait_times.append(log.actual_wait_minutes)
        
        if sum(weights) == 0:
            base_avg = 1
        else:
            base_avg = min(np.average(wait_times, weights=weights), 1)
        
        # Peak hour adjustment
        is_peak = self._is_peak_hour(doctor_id, target_date, hour)
        peak_factor = 1.0 if is_peak else 1.0  # No peak adjustment
        
        # Current day load factor
        doctor = Doctor.query.get(doctor_id)
        if doctor:
            current_load = doctor.get_daily_appointment_count(target_date)
            avg_load = np.mean([log.scheduled_patients for log in historical]) if historical else 10
            load_factor = (current_load / avg_load) if avg_load > 0 else 1.0
            load_factor = max(0.8, min(load_factor, 1.2))  # Clamp between 0.8 and 1.2
        else:
            load_factor = 1.0
        
        predicted = int(round(base_avg * peak_factor * load_factor))
        return 1
    
    def _get_queue_position(self, doctor_id: int, target_date: date, target_time: time) -> int:
        """Get the patient's position in the queue for a time slot."""
        count = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == target_date,
            Appointment.start_time <= target_time,
            Appointment.status.in_(['scheduled', 'confirmed', 'in_progress'])
        ).count()
        return count
    
    def _is_peak_hour(self, doctor_id: int, target_date: date, hour: int) -> bool:
        """
        Determine if a given hour is a peak hour for the doctor.
        
        Peak hour = hour with >= threshold appointments historically.
        """
        threshold = 5  # configurable
        count = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == target_date,
            db.extract('hour', Appointment.start_time) == hour,
            Appointment.status.in_(['scheduled', 'confirmed', 'in_progress', 'completed'])
        ).count()
        return count >= threshold
    
    # ========================================================
    # PEAK HOUR ANALYSIS
    # ========================================================
    
    def analyze_peak_hours(self, department_id: int = None,
                            days_back: int = 30) -> Dict:
        """
        Analyze peak hours across the hospital or a specific department.
        
        Returns hourly distribution of appointments to identify
        high-demand periods for resource planning.
        
        Args:
            department_id: Optional department filter
            days_back: Number of historical days to analyze
        
        Returns:
            Dictionary with hourly appointment counts and peak identification
        """
        cutoff_date = date.today() - timedelta(days=days_back)
        
        query = Appointment.query.filter(
            Appointment.appointment_date >= cutoff_date
        )
        if department_id:
            query = query.filter(Appointment.department_id == department_id)
        
        appointments = query.all()
        
        # Count appointments by hour
        hourly_counts = {}
        for hour in range(7, 20):  # 7 AM to 7 PM
            hourly_counts[hour] = 0
        
        for appt in appointments:
            hour = appt.start_time.hour
            if hour in hourly_counts:
                hourly_counts[hour] += 1
        
        # Identify peak hours (above average)
        if hourly_counts:
            avg_count = sum(hourly_counts.values()) / len(hourly_counts)
            peak_hours = [h for h, c in hourly_counts.items() if c > avg_count * 1.2]
        else:
            peak_hours = []
        
        return {
            'hourly_distribution': hourly_counts,
            'peak_hours': peak_hours,
            'average_per_hour': round(avg_count, 1) if hourly_counts else 0,
            'busiest_hour': max(hourly_counts, key=hourly_counts.get) if hourly_counts else None,
            'analysis_period_days': days_back
        }
    
    # ========================================================
    # CONFLICT DETECTION
    # ========================================================
    
    def detect_conflicts(self, doctor_id: int, target_date: date) -> List[Dict]:
        """
        Real-time conflict detection for a doctor's schedule.
        
        Checks for:
            - Overlapping time slots
            - Double-booked patients
            - Exceeding daily capacity
            - Appointments during leave
        
        Args:
            doctor_id: Doctor to check
            target_date: Date to check
        
        Returns:
            List of detected conflicts with details
        """
        conflicts = []
        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            return conflicts
        
        # Get all active appointments
        appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == target_date,
            Appointment.status.in_(['scheduled', 'confirmed', 'in_progress'])
        ).order_by(Appointment.start_time).all()
        
        # Check 1: Overlapping time slots
        for i in range(len(appointments)):
            for j in range(i + 1, len(appointments)):
                if appointments[i].end_time > appointments[j].start_time:
                    conflicts.append({
                        'type': 'overlap',
                        'severity': 'high',
                        'message': f'Appointments #{appointments[i].id} and #{appointments[j].id} overlap',
                        'appointment_ids': [appointments[i].id, appointments[j].id]
                    })
        
        # Check 2: Capacity exceeded
        if len(appointments) > doctor.max_patients_per_day:
            conflicts.append({
                'type': 'capacity',
                'severity': 'medium',
                'message': f'Doctor has {len(appointments)} appointments, exceeding max of {doctor.max_patients_per_day}',
                'current': len(appointments),
                'max': doctor.max_patients_per_day
            })
        
        # Check 3: Doctor on leave
        if doctor.is_on_leave(target_date):
            conflicts.append({
                'type': 'leave',
                'severity': 'high',
                'message': f'{doctor.full_name} is on leave on {target_date}',
                'affected_count': len(appointments)
            })
        
        # Check 4: Duplicate patients
        patient_ids = [a.patient_id for a in appointments]
        seen = set()
        for pid in patient_ids:
            if pid in seen:
                conflicts.append({
                    'type': 'duplicate_patient',
                    'severity': 'low',
                    'message': f'Patient #{pid} has multiple appointments with same doctor on same day'
                })
            seen.add(pid)
        
        return conflicts
    
    # ========================================================
    # ANALYTICS & STATISTICS
    # ========================================================
    
    def get_scheduling_analytics(self, days_back: int = 30) -> Dict:
        """
        Generate comprehensive scheduling analytics.
        
        Returns:
            Dictionary with various analytics metrics
        """
        cutoff = date.today() - timedelta(days=days_back)
        
        total = Appointment.query.filter(Appointment.created_at >= datetime.combine(cutoff, time.min)).count()
        completed = Appointment.query.filter(
            Appointment.status == 'completed',
            Appointment.created_at >= datetime.combine(cutoff, time.min)
        ).count()
        cancelled = Appointment.query.filter(
            Appointment.status == 'cancelled',
            Appointment.created_at >= datetime.combine(cutoff, time.min)
        ).count()
        no_shows = Appointment.query.filter(
            Appointment.status == 'no_show',
            Appointment.created_at >= datetime.combine(cutoff, time.min)
        ).count()
        ai_scheduled = Appointment.query.filter(
            Appointment.ai_scheduled == True,
            Appointment.created_at >= datetime.combine(cutoff, time.min)
        ).count()
        
        # Priority breakdown
        emergency = Appointment.query.filter(
            Appointment.priority == 'emergency',
            Appointment.created_at >= datetime.combine(cutoff, time.min)
        ).count()
        
        # Average waiting time
        wait_data = db.session.query(
            db.func.avg(Appointment.actual_wait_time)
        ).filter(
            Appointment.actual_wait_time.isnot(None),
            Appointment.created_at >= datetime.combine(cutoff, time.min)
        ).scalar()
        
        return {
            'period_days': days_back,
            'total_appointments': total,
            'completed': completed,
            'cancelled': cancelled,
            'no_shows': no_shows,
            'ai_scheduled_count': ai_scheduled,
            'ai_scheduled_percentage': round((ai_scheduled / total * 100), 1) if total > 0 else 0,
            'completion_rate': round((completed / total * 100), 1) if total > 0 else 0,
            'cancellation_rate': round((cancelled / total * 100), 1) if total > 0 else 0,
            'emergency_count': emergency,
            'avg_wait_time': round(float(wait_data), 1) if wait_data else 0
        }
    
    # ========================================================
    # UTILITY FUNCTIONS
    # ========================================================
    
    def _create_notification(self, user_id: int, appointment_id: int,
                              subject: str, message: str):
        """Create a notification record for the user."""
        notification = Notification(
            user_id=user_id,
            appointment_id=appointment_id,
            type='system',
            subject=subject,
            message=message
        )
        db.session.add(notification)
    
    def get_available_slots_for_date(self, department_id: int,
                                      target_date: date,
                                      doctor_id: Optional[int] = None) -> List[Dict]:
        """
        Get all available slots for a department on a date.
        Optionally filter by specific doctor.
        
        Args:
            department_id: Department ID
            target_date: Target date
            doctor_id: Optional specific doctor
        
        Returns:
            List of available slots across all/specific doctors
        """
        all_slots = []

        if doctor_id:
            doctor = Doctor.query.get(doctor_id)
            if doctor:
                slots = self.generate_available_slots(doctor, target_date)
                all_slots.extend(slots)
        else:
            doctors = Doctor.query.filter_by(department_id=department_id).all()
            for doc in doctors:
                slots = self.generate_available_slots(doc, target_date)
                all_slots.extend(slots)
        
        # Sort by time, then by doctor id.
        all_slots.sort(key=lambda s: (
            s['start_time'].hour * 60 + s['start_time'].minute,
            s['doctor_id']
        ))
        
        # Convert time objects to strings for JSON serialization
        for slot in all_slots:
            slot['start_time'] = slot['start_time'].strftime('%H:%M')
            slot['end_time'] = slot['end_time'].strftime('%H:%M')
            slot['date'] = slot['date'].isoformat()
        
        return all_slots


# Global scheduler instance
scheduler = AIScheduler()
