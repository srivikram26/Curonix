-- ============================================================
-- AI-Based Hospital Appointment Scheduling System
-- Database Schema - MySQL
-- ============================================================
-- This script creates all necessary tables for the system.
-- Run this script after creating the database.
-- ============================================================

-- Create the database
CREATE DATABASE IF NOT EXISTS hospital_scheduler
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE hospital_scheduler;

-- ============================================================
-- TABLE: departments
-- Stores hospital departments (e.g., Cardiology, Neurology)
-- ============================================================
CREATE TABLE IF NOT EXISTS departments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    floor_number INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_dept_active (is_active)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: users
-- Stores all users: patients, doctors, and admins
-- Role-based access control via 'role' column
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role ENUM('patient', 'doctor', 'admin') NOT NULL DEFAULT 'patient',
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    gender ENUM('male', 'female', 'other'),
    blood_group VARCHAR(5),
    address TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_senior_citizen BOOLEAN DEFAULT FALSE,
    profile_image VARCHAR(255),
    last_login TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_role (role),
    INDEX idx_user_email (email),
    INDEX idx_user_active (is_active)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: doctors
-- Extended doctor profile linked to users table
-- ============================================================
CREATE TABLE IF NOT EXISTS doctors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    department_id INT NOT NULL,
    specialization VARCHAR(200),
    qualification VARCHAR(300),
    experience_years INT DEFAULT 0,
    consultation_fee DECIMAL(10, 2) DEFAULT 0.00,
    max_patients_per_day INT DEFAULT 20,
    avg_consultation_time INT DEFAULT 30,  -- in minutes
    rating DECIMAL(3, 2) DEFAULT 0.00,
    bio TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
    INDEX idx_doc_dept (department_id),
    INDEX idx_doc_user (user_id)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: doctor_availability
-- Stores weekly availability schedule for each doctor
-- ============================================================
CREATE TABLE IF NOT EXISTS doctor_availability (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id INT NOT NULL,
    day_of_week TINYINT NOT NULL,  -- 0=Monday, 6=Sunday
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    max_slots INT DEFAULT 16,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    INDEX idx_avail_doctor (doctor_id),
    INDEX idx_avail_day (day_of_week),
    UNIQUE KEY unique_doctor_day (doctor_id, day_of_week)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: doctor_leaves
-- Stores doctor leave/unavailability dates
-- ============================================================
CREATE TABLE IF NOT EXISTS doctor_leaves (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id INT NOT NULL,
    leave_date DATE NOT NULL,
    reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    UNIQUE KEY unique_doctor_leave (doctor_id, leave_date)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: appointments
-- Core appointment records with AI scheduling metadata
-- ============================================================
CREATE TABLE IF NOT EXISTS appointments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    department_id INT NOT NULL,
    location VARCHAR(150) DEFAULT 'Main Campus Hospital',
    appointment_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status ENUM('scheduled', 'confirmed', 'in_progress', 'completed',
                'cancelled', 'no_show', 'rescheduled') DEFAULT 'scheduled',
    priority ENUM('emergency', 'senior_citizen', 'follow_up', 'normal') DEFAULT 'normal',
    priority_score INT DEFAULT 10,       -- Computed by AI scheduler
    appointment_type ENUM('new', 'follow_up', 'emergency') DEFAULT 'new',
    symptoms TEXT,
    notes TEXT,
    ai_scheduled BOOLEAN DEFAULT FALSE,   -- Whether AI assigned the slot
    estimated_wait_time INT DEFAULT 0,     -- AI-predicted wait in minutes
    actual_wait_time INT NULL,
    cancellation_reason TEXT,
    rescheduled_from INT NULL,            -- Original appointment ID if rescheduled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
    FOREIGN KEY (rescheduled_from) REFERENCES appointments(id) ON DELETE SET NULL,
    INDEX idx_appt_patient (patient_id),
    INDEX idx_appt_doctor (doctor_id),
    INDEX idx_appt_date (appointment_date),
    INDEX idx_appt_status (status),
    INDEX idx_appt_priority (priority_score DESC),
    INDEX idx_appt_dept_date (department_id, appointment_date)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: appointment_history
-- Audit trail for appointment changes
-- ============================================================
CREATE TABLE IF NOT EXISTS appointment_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    appointment_id INT NOT NULL,
    changed_by INT,
    old_status VARCHAR(50),
    new_status VARCHAR(50),
    old_date DATE,
    new_date DATE,
    old_time TIME,
    new_time TIME,
    change_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_hist_appt (appointment_id)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: waiting_time_log
-- Historical data for AI waiting-time prediction model
-- ============================================================
CREATE TABLE IF NOT EXISTS waiting_time_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id INT NOT NULL,
    department_id INT NOT NULL,
    appointment_date DATE NOT NULL,
    time_slot TIME NOT NULL,
    day_of_week TINYINT NOT NULL,
    hour_of_day TINYINT NOT NULL,
    scheduled_patients INT DEFAULT 0,
    actual_wait_minutes INT DEFAULT 0,
    is_peak_hour BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
    INDEX idx_wait_doctor (doctor_id),
    INDEX idx_wait_date (appointment_date)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: notifications
-- SMS/Email notification simulation log
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    appointment_id INT,
    type ENUM('email', 'sms', 'system') DEFAULT 'system',
    subject VARCHAR(255),
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL,
    INDEX idx_notif_user (user_id),
    INDEX idx_notif_read (is_read)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: system_settings
-- Configurable system parameters
-- ============================================================
CREATE TABLE IF NOT EXISTS system_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) NOT NULL UNIQUE,
    setting_value TEXT NOT NULL,
    description VARCHAR(255),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================================
-- Insert default system settings
-- ============================================================
INSERT INTO system_settings (setting_key, setting_value, description) VALUES
('slot_duration', '30', 'Default appointment slot duration in minutes'),
('working_hours_start', '09:00', 'Hospital working hours start time'),
('working_hours_end', '17:00', 'Hospital working hours end time'),
('max_advance_booking_days', '30', 'Maximum days in advance for booking'),
('auto_reschedule_enabled', 'true', 'Enable AI auto-rescheduling on cancellation'),
('emergency_slots_reserved', '2', 'Number of emergency slots reserved per doctor per day'),
('peak_hour_threshold', '5', 'Number of appointments to classify as peak hour');
