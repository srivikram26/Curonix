"""
Database Seeder — Sample Test Data
====================================
Creates sample departments, users (admin/doctor/patient), doctor profiles,
availability slots, and appointments for testing and demonstration.

Usage:
    python seed_data.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, date, time, timedelta
from werkzeug.security import generate_password_hash
from app.factory import create_app
from app.models import (
    db, User, Doctor, Department, DoctorAvailability,
    Appointment, WaitingTimeLog, Notification
)
import random

BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']
HOSPITAL_BRANCHES = [
    'Main Campus Hospital',
    'North Care Hospital',
    'South Specialty Center',
]


def seed():
    app = create_app()
    with app.app_context():
        print("🗑️  Clearing existing data...")
        # Order matters for foreign keys
        Notification.query.delete()
        WaitingTimeLog.query.delete()
        Appointment.query.delete()
        DoctorAvailability.query.delete()
        Doctor.query.delete()
        User.query.delete()
        Department.query.delete()
        db.session.commit()

        # ── 1. Departments ──────────────────────────────────────────
        print("🏥 Creating departments...")
        departments_data = [
            ("General Medicine", "Primary healthcare and general consultations"),
            ("Cardiology", "Heart and cardiovascular system specialists"),
            ("Orthopedics", "Bone, joint, and musculoskeletal care"),
            ("Pediatrics", "Healthcare for infants, children, and adolescents"),
            ("Dermatology", "Skin, hair, and nail conditions"),
            ("Neurology", "Brain and nervous system disorders"),
            ("ENT", "Ear, Nose, and Throat specialists"),
            ("Ophthalmology", "Eye care and vision specialists"),
            ("Gynecology", "Women's reproductive health and prenatal care"),
            ("Urology", "Urinary tract and male reproductive system care"),
            ("Pulmonology", "Lung and respiratory system disorders"),
            ("Psychiatry", "Mental health and behavioral medicine"),
        ]
        departments = []
        for name, desc in departments_data:
            dept = Department(name=name, description=desc, is_active=True)
            db.session.add(dept)
            departments.append(dept)
        db.session.flush()

        # ── 2. Admin User ───────────────────────────────────────────
        print("👤 Creating admin user...")
        admin = User(
            first_name="System",
            last_name="Admin",
            email="admin@hospital.com",
            password_hash=generate_password_hash("admin123"),
            role="admin",
            phone="9999999999",
            is_active=True
        )
        db.session.add(admin)

        # ── 3. Doctor Users & Profiles ──────────────────────────────
        print("👨‍⚕️ Creating doctors...")
        doctors_data = [
            ("Arun", "Kumar", "arun@hospital.com", "9876543201", departments[0], "General Physician", 25, 20),
            ("Priya", "Sharma", "priya@hospital.com", "9876543202", departments[1], "Cardiologist", 30, 15),
            ("Rajesh", "Patel", "rajesh@hospital.com", "9876543203", departments[2], "Orthopedic Surgeon", 30, 18),
            ("Sneha", "Reddy", "sneha@hospital.com", "9876543204", departments[3], "Pediatrician", 20, 22),
            ("Mohammed", "Ali", "ali@hospital.com", "9876543205", departments[4], "Dermatologist", 20, 20),
            ("Kavitha", "Nair", "kavitha@hospital.com", "9876543206", departments[5], "Neurologist", 30, 15),
            ("Suresh", "Babu", "suresh@hospital.com", "9876543207", departments[6], "ENT Specialist", 20, 20),
            ("Lakshmi", "Iyer", "lakshmi@hospital.com", "9876543208", departments[7], "Ophthalmologist", 20, 18),

            # Additional doctors (2 more per department)
            ("Neha", "Gupta", "neha.gupta@hospital.com", "9876543209", departments[0], "Family Medicine", 20, 22),
            ("Rohan", "Mehta", "rohan.mehta@hospital.com", "9876543210", departments[0], "Internal Medicine", 25, 20),

            ("Vikram", "Joshi", "vikram.joshi@hospital.com", "9876543211", departments[1], "Interventional Cardiologist", 30, 16),
            ("Ananya", "Rao", "ananya.rao@hospital.com", "9876543212", departments[1], "Cardiac Electrophysiologist", 30, 14),

            ("Deepak", "Mishra", "deepak.mishra@hospital.com", "9876543213", departments[2], "Joint Replacement Surgeon", 30, 18),
            ("Pooja", "Nambiar", "pooja.nambiar@hospital.com", "9876543214", departments[2], "Sports Orthopedics", 25, 20),

            ("Harini", "Menon", "harini.menon@hospital.com", "9876543215", departments[3], "Neonatologist", 20, 24),
            ("Aditya", "Kulkarni", "aditya.kulkarni@hospital.com", "9876543216", departments[3], "Pediatric Pulmonologist", 25, 20),

            ("Farah", "Siddiqui", "farah.siddiqui@hospital.com", "9876543217", departments[4], "Cosmetic Dermatologist", 20, 22),
            ("Nikhil", "Bose", "nikhil.bose@hospital.com", "9876543218", departments[4], "Trichologist", 20, 20),

            ("Sharath", "Krishnan", "sharath.krishnan@hospital.com", "9876543219", departments[5], "Stroke Specialist", 30, 15),
            ("Ishita", "Sen", "ishita.sen@hospital.com", "9876543220", departments[5], "Neurophysician", 25, 18),

            ("Manoj", "Pillai", "manoj.pillai@hospital.com", "9876543221", departments[6], "Otologist", 20, 20),
            ("Divya", "Prakash", "divya.prakash@hospital.com", "9876543222", departments[6], "Rhinologist", 20, 22),

            ("Girish", "Shetty", "girish.shetty@hospital.com", "9876543223", departments[7], "Retina Specialist", 20, 18),
            ("Meenal", "Kapoor", "meenal.kapoor@hospital.com", "9876543224", departments[7], "Glaucoma Specialist", 20, 20),

            ("Anita", "Deshpande", "anita.deshpande@hospital.com", "9876543225", departments[8], "Gynecologist", 25, 20),
            ("Ritu", "Chawla", "ritu.chawla@hospital.com", "9876543226", departments[8], "Obstetrician", 30, 18),

            ("Pranav", "Mohan", "pranav.mohan@hospital.com", "9876543227", departments[9], "Urologist", 25, 20),
            ("Sameera", "Iqbal", "sameera.iqbal@hospital.com", "9876543228", departments[9], "Andrologist", 25, 18),

            ("Naveen", "Rathod", "naveen.rathod@hospital.com", "9876543229", departments[10], "Pulmonologist", 30, 16),
            ("Bhavana", "Roy", "bhavana.roy@hospital.com", "9876543230", departments[10], "Respiratory Specialist", 25, 18),

            ("Kiran", "Saxena", "kiran.saxena@hospital.com", "9876543231", departments[11], "Psychiatrist", 30, 16),
            ("Maya", "Thomas", "maya.thomas@hospital.com", "9876543232", departments[11], "Child Psychiatrist", 30, 14),

            # Additional doctors (1 more per department)
            ("Sanjay", "Arora", "sanjay.arora@hospital.com", "9876543233", departments[0], "General Physician", 20, 24),
            ("Leena", "Mathew", "leena.mathew@hospital.com", "9876543234", departments[1], "Preventive Cardiologist", 25, 18),
            ("Tarun", "Bhat", "tarun.bhat@hospital.com", "9876543235", departments[2], "Trauma Orthopedics", 30, 20),
            ("Nisha", "Varma", "nisha.varma@hospital.com", "9876543236", departments[3], "Pediatric Specialist", 20, 24),
            ("Aarav", "Ghosh", "aarav.ghosh@hospital.com", "9876543237", departments[4], "Clinical Dermatologist", 20, 22),
            ("Ritika", "Paul", "ritika.paul@hospital.com", "9876543238", departments[5], "Epilepsy Specialist", 30, 16),
            ("Yogesh", "Naidu", "yogesh.naidu@hospital.com", "9876543239", departments[6], "Laryngologist", 20, 20),
            ("Charu", "Bansal", "charu.bansal@hospital.com", "9876543240", departments[7], "Cornea Specialist", 20, 18),
            ("Pallavi", "Rane", "pallavi.rane@hospital.com", "9876543241", departments[8], "Obstetrician", 25, 20),
            ("Harsh", "Agarwal", "harsh.agarwal@hospital.com", "9876543242", departments[9], "Uro-Oncologist", 30, 16),
            ("Sonia", "Fernandes", "sonia.fernandes@hospital.com", "9876543243", departments[10], "Critical Care Pulmonologist", 30, 16),
            ("Imran", "Qureshi", "imran.qureshi@hospital.com", "9876543244", departments[11], "Consultant Psychiatrist", 30, 16),

            # Ensure minimum 5 doctors in every department
            ("Dev", "Malhotra", "dev.malhotra@hospital.com", "9876543245", departments[0], "Primary Care Specialist", 20, 24),
            ("Mitali", "Saha", "mitali.saha@hospital.com", "9876543246", departments[1], "Heart Failure Specialist", 30, 16),
            ("Ramesh", "Ilango", "ramesh.ilango@hospital.com", "9876543247", departments[2], "Spine Surgeon", 30, 18),
            ("Keerthi", "Shenoy", "keerthi.shenoy@hospital.com", "9876543248", departments[3], "Pediatric Endocrinologist", 25, 20),
            ("Manasi", "Kulshreshtha", "manasi.kulshreshtha@hospital.com", "9876543249", departments[4], "Dermatosurgeon", 25, 18),
            ("Akshay", "Dua", "akshay.dua@hospital.com", "9876543250", departments[5], "Movement Disorder Specialist", 30, 16),
            ("Rekha", "Muralidhar", "rekha.muralidhar@hospital.com", "9876543251", departments[6], "Head and Neck ENT", 20, 20),
            ("Vani", "Trivedi", "vani.trivedi@hospital.com", "9876543252", departments[7], "Pediatric Ophthalmologist", 20, 18),

            ("Shruti", "Bedi", "shruti.bedi@hospital.com", "9876543253", departments[8], "Reproductive Endocrinologist", 30, 16),
            ("Nitin", "Purohit", "nitin.purohit@hospital.com", "9876543254", departments[8], "Maternal Fetal Specialist", 30, 14),

            ("Gautam", "Lal", "gautam.lal@hospital.com", "9876543255", departments[9], "Reconstructive Urologist", 30, 16),
            ("Tejas", "Kale", "tejas.kale@hospital.com", "9876543256", departments[9], "Endourologist", 25, 18),

            ("Rupal", "Dey", "rupal.dey@hospital.com", "9876543257", departments[10], "Sleep Medicine Specialist", 25, 18),
            ("Keshav", "Mitra", "keshav.mitra@hospital.com", "9876543258", departments[10], "Interventional Pulmonologist", 30, 16),

            ("Ayesha", "Parveen", "ayesha.parveen@hospital.com", "9876543259", departments[11], "Addiction Psychiatrist", 30, 14),
            ("Rohit", "Menaria", "rohit.menaria@hospital.com", "9876543260", departments[11], "Neuropsychiatrist", 30, 16),
        ]
        doctors = []
        for index, (first, last, email, phone, dept, spec, duration, max_p) in enumerate(doctors_data):
            branch_name = HOSPITAL_BRANCHES[index % len(HOSPITAL_BRANCHES)]
            user = User(
                first_name=first, last_name=last, email=email,
                password_hash=generate_password_hash("doctor123"),
                role="doctor", phone=phone, is_active=True,
                address=branch_name
            )
            db.session.add(user)
            db.session.flush()

            doctor = Doctor(
                user_id=user.id,
                department_id=dept.id,
                specialization=spec,
                avg_consultation_time=duration,
                max_patients_per_day=max_p
            )
            db.session.add(doctor)
            doctors.append(doctor)
        db.session.flush()

        # ── 4. Doctor Availability (Mon–Fri 9–17, Sat 9–13) ────────
        print("⏰ Setting doctor availability...")
        for doctor in doctors:
            for day in range(6):  # 0=Monday to 5=Saturday
                avail = DoctorAvailability(
                    doctor_id=doctor.id,
                    day_of_week=day,
                    start_time=time(9, 0),
                    end_time=time(13, 0) if day == 5 else time(17, 0),
                    is_available=True
                )
                db.session.add(avail)
            # Sunday off
            avail = DoctorAvailability(
                doctor_id=doctor.id,
                day_of_week=6,
                start_time=time(9, 0),
                end_time=time(17, 0),
                is_available=False
            )
            db.session.add(avail)

        # ── 5. Patient Users ────────────────────────────────────────
        print("🧑 Creating patients...")
        patients_data = [
            ("Rahul", "Verma", "rahul@test.com", "9000000001", date(1990, 5, 15), "male"),
            ("Anita", "Singh", "anita@test.com", "9000000002", date(1985, 8, 22), "female"),
            ("Vijay", "Kumar", "vijay@test.com", "9000000003", date(1955, 3, 10), "male"),      # Senior citizen
            ("Meera", "Joshi", "meera@test.com", "9000000004", date(1992, 11, 30), "female"),
            ("Karthik", "Rajan", "karthik@test.com", "9000000005", date(1960, 1, 5), "male"),   # Senior citizen
            ("Deepa", "Menon", "deepa@test.com", "9000000006", date(1998, 7, 18), "female"),
            ("Amit", "Tiwari", "amit@test.com", "9000000007", date(1988, 9, 25), "male"),
            ("Shalini", "Das", "shalini@test.com", "9000000008", date(1975, 12, 2), "female"),
            ("Arjun", "Nair", "arjun@test.com", "9000000009", date(2000, 4, 14), "male"),
            ("Fatima", "Khan", "fatima@test.com", "9000000010", date(1965, 6, 8), "female"),
            ("Patient", "Demo", "patient@hospital.com", "9000000011", date(1995, 1, 1), "male"),
        ]
        patients = []
        for first, last, email, phone, dob, gender in patients_data:
            user = User(
                first_name=first, last_name=last, email=email,
                password_hash=generate_password_hash("patient123"),
                role="patient", phone=phone,
                date_of_birth=dob, gender=gender,
                is_active=True
            )
            # Auto-detect senior citizen
            user.calculate_senior_citizen()
            user.blood_group = random.choice(BLOOD_GROUPS)
            db.session.add(user)
            patients.append(user)
        db.session.flush()

        # ── 6. Sample Appointments ──────────────────────────────────
        print("📋 Creating sample appointments...")
        today = date.today()
        appointments_data = [
            # Past completed appointments
            (patients[0], doctors[0], today - timedelta(days=10), time(9, 0), time(9, 25), "completed", "new", "normal", "Fever and cold", 15),
            (patients[1], doctors[1], today - timedelta(days=8), time(10, 0), time(10, 30), "completed", "new", "normal", "Chest pain follow-up", 25),
            (patients[2], doctors[0], today - timedelta(days=7), time(11, 0), time(11, 25), "completed", "new", "senior_citizen", "Blood pressure check", 60),
            (patients[3], doctors[3], today - timedelta(days=5), time(9, 30), time(9, 50), "completed", "new", "normal", "Child vaccination", 20),
            (patients[4], doctors[2], today - timedelta(days=4), time(14, 0), time(14, 30), "completed", "follow_up", "senior_citizen", "Knee pain follow-up", 45),
            (patients[5], doctors[4], today - timedelta(days=3), time(11, 0), time(11, 20), "completed", "new", "normal", "Skin rash", 12),
            (patients[6], doctors[5], today - timedelta(days=2), time(10, 0), time(10, 30), "completed", "new", "normal", "Frequent headaches", 30),

            # Today's appointments
            (patients[0], doctors[0], today, time(9, 0), time(9, 25), "confirmed", "follow_up", "normal", "Fever follow-up", 30),
            (patients[7], doctors[1], today, time(10, 0), time(10, 30), "scheduled", "new", "normal", "Heart palpitations", 20),
            (patients[2], doctors[2], today, time(11, 0), time(11, 30), "scheduled", "new", "senior_citizen", "Hip joint pain", 55),
            (patients[8], doctors[3], today, time(14, 0), time(14, 20), "scheduled", "new", "normal", "Child ear infection", 18),

            # Upcoming appointments
            (patients[1], doctors[0], today + timedelta(days=1), time(9, 0), time(9, 25), "scheduled", "new", "normal", "General checkup", 10),
            (patients[3], doctors[4], today + timedelta(days=1), time(10, 0), time(10, 20), "scheduled", "new", "normal", "Acne treatment", 15),
            (patients[9], doctors[5], today + timedelta(days=2), time(11, 0), time(11, 30), "scheduled", "new", "normal", "Numbness in hands", 22),
            (patients[4], doctors[6], today + timedelta(days=2), time(14, 0), time(14, 20), "scheduled", "new", "senior_citizen", "Sinus problems", 40),
            (patients[5], doctors[7], today + timedelta(days=3), time(9, 0), time(9, 20), "scheduled", "new", "normal", "Eye checkup", 10),

            # Cancelled appointment
            (patients[6], doctors[0], today - timedelta(days=1), time(15, 0), time(15, 25), "cancelled", "new", "normal", "General checkup", 10),
        ]

        for patient, doctor, appt_date, start, end, status, appt_type, priority, symptoms, score in appointments_data:
            appt = Appointment(
                patient_id=patient.id,
                doctor_id=doctor.id,
                department_id=doctor.department_id,
                appointment_date=appt_date,
                start_time=start,
                end_time=end,
                status=status,
                appointment_type=appt_type,
                priority=priority,
                symptoms=symptoms,
                priority_score=score,
                ai_scheduled=True,
                created_at=datetime.utcnow()
            )
            db.session.add(appt)

        # ── 7. Waiting Time Logs ────────────────────────────────────
        print("⏱️  Creating waiting time logs...")
        for i in range(15):
            log_date = today - timedelta(days=i)
            for doctor in doctors[:4]:
                hour = 9 + (i % 8)
                log = WaitingTimeLog(
                    doctor_id=doctor.id,
                    department_id=doctor.department_id,
                    appointment_date=log_date,
                    time_slot=time(hour, 0),
                    day_of_week=log_date.weekday(),
                    hour_of_day=hour,
                    scheduled_patients=max(5, 15 - i + doctor.id % 4),
                    actual_wait_minutes=int(10 + (i % 5) * 3 + (doctor.id % 3) * 5),
                    is_peak_hour=(10 <= hour <= 12),
                    created_at=datetime.utcnow()
                )
                db.session.add(log)

        # ── 8. Sample Notifications ─────────────────────────────────
        print("🔔 Creating sample notifications...")
        for patient in patients[:5]:
            notif = Notification(
                user_id=patient.id,
                subject="Welcome to Hospital Scheduler",
                message="Your account has been created. You can now book appointments with our AI-powered scheduling system.",
                type="system",
                is_read=False,
                sent_at=datetime.utcnow()
            )
            db.session.add(notif)

        # ── Commit everything ───────────────────────────────────────
        db.session.commit()

        print("\n✅ Database seeded successfully!")
        print("=" * 50)
        print("📋 DEMO CREDENTIALS:")
        print("-" * 50)
        print("  Admin:   admin@hospital.com     / admin123")
        print("  Doctor:  arun@hospital.com      / doctor123")
        print("  Doctor:  priya@hospital.com     / doctor123")
        print("  Patient: patient@hospital.com   / patient123")
        print("  Patient: rahul@test.com         / patient123")
        print("=" * 50)
        print(f"  Departments: {len(departments_data)}")
        print(f"  Doctors:     {len(doctors_data)}")
        print(f"  Patients:    {len(patients_data)}")
        print(f"  Appointments:{len(appointments_data)}")
        print("=" * 50)


if __name__ == "__main__":
    seed()
