# AI-Based Hospital Appointment Scheduling System

> **Final Year Capstone Project** — AI-powered hospital appointment scheduling using Constraint Satisfaction Problem (CSP) planning techniques, built with Flask, MySQL, and vanilla JavaScript.

---

## 📁 Project Structure

```
hospital-appointment-system/
├── app/
│   ├── __init__.py              # Package init
│   ├── factory.py               # Flask application factory
│   ├── models.py                # SQLAlchemy ORM models
│   ├── ai_scheduler.py          # AI scheduling engine (CSP, priority, workload)
│   ├── notifications.py         # Notification simulation service
│   └── routes/
│       ├── __init__.py
│       ├── main_routes.py       # Landing & about pages
│       ├── auth_routes.py       # Login, register, logout
│       ├── patient_routes.py    # Patient dashboard & booking API
│       ├── doctor_routes.py     # Doctor schedule & management API
│       ├── admin_routes.py      # Admin dashboard & analytics API
│       └── api_routes.py        # Public API endpoints
├── database/
│   └── schema.sql               # MySQL database schema
├── static/
│   ├── css/style.css            # Complete stylesheet
│   └── js/app.js                # Core JavaScript utilities
├── templates/
│   ├── base.html                # Base HTML template
│   ├── dashboard_base.html      # Dashboard layout (sidebar + content)
│   ├── index.html               # Landing page
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   ├── patient/
│   │   ├── dashboard.html
│   │   ├── book_appointment.html
│   │   ├── appointments.html
│   │   └── profile.html
│   ├── doctor/
│   │   ├── dashboard.html
│   │   ├── schedule.html
│   │   ├── availability.html
│   │   └── patients.html
│   └── admin/
│       ├── dashboard.html
│       ├── doctors.html
│       ├── departments.html
│       ├── appointments.html
│       └── analytics.html
├── config.py                    # Flask configuration
├── run.py                       # Application entry point
├── seed_data.py                 # Database seeder with sample data
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variable template
├── DOCUMENTATION.md             # Full project documentation
└── README.md                    # This file
```

---

## 🚀 Setup Instructions

### Prerequisites
- **Python 3.9+**
- **MySQL 8.0+** (or MariaDB 10.5+)
- **pip** (Python package manager)
- **Git** (optional)

### Step 1: Clone / Extract the Project
```bash
cd hospital-appointment-system
```

### Step 2: Create a Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Set Up MySQL Database
1. Open MySQL command line or MySQL Workbench.
2. Create the database:
```sql
CREATE DATABASE hospital_scheduler CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'hospital_user'@'localhost' IDENTIFIED BY 'hospital_pass';
GRANT ALL PRIVILEGES ON hospital_scheduler.* TO 'hospital_user'@'localhost';
FLUSH PRIVILEGES;
```
3. Import the schema:
```bash
mysql -u hospital_user -p hospital_scheduler < database/schema.sql
```

### Step 5: Configure Environment Variables
```bash
# Copy the example env file
copy .env.example .env        # Windows
cp .env.example .env          # macOS/Linux

# Edit .env with your MySQL credentials
# MYSQL_USER=hospital_user
# MYSQL_PASSWORD=hospital_pass
# MYSQL_HOST=localhost
# MYSQL_DB=hospital_scheduler
```

### Step 6: Seed the Database with Sample Data
```bash
python seed_data.py
```

### Step 7: Run the Application
```bash
python run.py
```

Visit: **http://localhost:5000**

---

## 🔐 Demo Credentials

| Role    | Email                   | Password    |
|---------|-------------------------|-------------|
| Admin   | admin@hospital.com      | admin123    |
| Doctor  | arun@hospital.com       | doctor123   |
| Doctor  | priya@hospital.com      | doctor123   |
| Patient | patient@hospital.com    | patient123  |
| Patient | rahul@test.com          | patient123  |

---

## ✨ Key Features

### Patient Portal
- AI-powered appointment booking with smart slot recommendations
- Priority-based scheduling (Emergency, Senior Citizen, Follow-up, Regular)
- Real-time wait time prediction
- Appointment management (view, cancel, reschedule)
- Notification center

### Doctor Portal
- Daily/weekly schedule management
- Availability and leave management
- Patient history and visit tracking
- Emergency appointment handling
- Workload monitoring with conflict detection

### Admin Dashboard
- System-wide analytics with Chart.js visualizations
- Doctor and department CRUD management
- AI scheduling analytics (peak hours, workload distribution, priority stats)
- Conflict detection and resolution
- Appointment oversight with advanced filters

### AI Scheduling Engine
- **CSP (Constraint Satisfaction Problem):** 5 hard constraints for slot generation
- **Priority Scoring:** Weighted priority system (Emergency=100, Senior=50, Follow-up=30)
- **Workload Balancing:** Min-heap algorithm for fair doctor allocation
- **Wait Time Prediction:** Weighted moving average with peak/load factors
- **Auto-Rescheduling:** Greedy compaction on cancellations
- **Conflict Detection:** Overlapping appointment identification

---

## 🛠️ Technology Stack

| Layer      | Technology                    |
|------------|-------------------------------|
| Backend    | Python 3.9+, Flask 3.0       |
| Database   | MySQL 8.0, SQLAlchemy ORM     |
| AI/ML      | NumPy, SciPy, scikit-learn    |
| Frontend   | HTML5, CSS3, Vanilla JS       |
| Charts     | Chart.js 4.x                  |
| Auth       | Flask-Login, Werkzeug hashing |

---

## 🧪 Testing

### Quick Smoke Test
1. Login as patient → Book an appointment → Verify AI slot selection
2. Login as doctor → Check today's schedule → Update appointment status
3. Login as admin → View analytics → Check AI scheduling stats

### API Endpoints Test
```bash
# Health check
curl http://localhost:5000/api/health

# List departments
curl http://localhost:5000/api/departments

# List doctors for a department
curl http://localhost:5000/api/doctors?department_id=1
```

---

## Deploy on Render

### Option A: Blueprint deploy (recommended)
1. Push this project to GitHub (already done in your case).
2. In Render, click **New +** -> **Blueprint**.
3. Select your repository and deploy. Render will use `render.yaml` automatically.

> This repository also includes a root-level `render.yaml` that points to `nit/hospital-appointment-system`, so Blueprint deploy works even when this app is in a subfolder.

### Option B: Manual Web Service deploy
If you prefer creating the service manually in Render, use:

- **Environment**: Python
- **Root Directory**: `nit/hospital-appointment-system`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`

### Required Environment Variables
Set these in Render -> your service -> **Environment**:

- `APP_ENV=production`
- `SECRET_KEY=<strong-random-value>`
- `JWT_SECRET_KEY=<strong-random-value>`
- `DATABASE_URL=<your-db-connection-string>`
- `DOCTOR_ALLOWED_EMAIL_DOMAINS=hospital.com`

### Database Notes
- The app supports SQLite by default for local development.
- For production on Render, use an external persistent SQL database and set `DATABASE_URL`.
- Postgres URLs in either `postgres://...` or `postgresql://...` format are supported.
- Example MySQL URL format:

```text
mysql+pymysql://username:password@host:3306/hospital_scheduler
```

### After First Deploy
1. Open your Render service URL.
2. Verify health endpoint:

```bash
curl https://<your-render-service>.onrender.com/api/health
```

3. If database is empty, run seeding once using a Render Shell session:

```bash
python seed_data.py
```

---

## 📄 License

This project is developed as a final-year capstone project for academic purposes.
