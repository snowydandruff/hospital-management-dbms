from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime, date
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Database setup
def init_db():
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            user_type TEXT NOT NULL,
            phone TEXT,
            specialization TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Appointments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_date DATE NOT NULL,
            appointment_time TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES users (id),
            FOREIGN KEY (doctor_id) REFERENCES users (id)
        )
    ''')
    
    # Medical records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medical_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            diagnosis TEXT,
            prescription TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (appointment_id) REFERENCES appointments (id),
            FOREIGN KEY (patient_id) REFERENCES users (id),
            FOREIGN KEY (doctor_id) REFERENCES users (id)
        )
    ''')
    
    # Departments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            head_doctor_id INTEGER,
            phone TEXT,
            location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (head_doctor_id) REFERENCES users (id)
        )
    ''')
    
    # Medications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            generic_name TEXT,
            description TEXT,
            dosage TEXT,
            side_effects TEXT,
            price REAL,
            stock_quantity INTEGER DEFAULT 0,
            manufacturer TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Insert some sample departments
    cursor.execute('SELECT COUNT(*) FROM departments')
    if cursor.fetchone()[0] == 0:
        sample_departments = [
            ('Cardiology', 'Heart and cardiovascular system care', None, '+1-555-0101', 'Building A, Floor 3'),
            ('Neurology', 'Brain and nervous system disorders', None, '+1-555-0102', 'Building B, Floor 2'),
            ('Orthopedics', 'Bone, joint, and muscle treatment', None, '+1-555-0103', 'Building A, Floor 1'),
            ('Pediatrics', 'Medical care for infants and children', None, '+1-555-0104', 'Building C, Floor 1'),
            ('Emergency', '24/7 emergency medical services', None, '+1-555-0105', 'Building A, Ground Floor'),
            ('General Medicine', 'Primary healthcare and general treatment', None, '+1-555-0106', 'Building B, Floor 1')
        ]
        cursor.executemany('''
            INSERT INTO departments (name, description, head_doctor_id, phone, location)
            VALUES (?, ?, ?, ?, ?)
        ''', sample_departments)
    
    # Insert some sample medications
    cursor.execute('SELECT COUNT(*) FROM medications')
    if cursor.fetchone()[0] == 0:
        sample_medications = [
            ('Paracetamol', 'Acetaminophen', 'Pain reliever and fever reducer', '500mg tablets', 'Nausea, liver damage in overdose', 5.99, 100, 'PharmaCorp'),
            ('Ibuprofen', 'Ibuprofen', 'Anti-inflammatory pain reliever', '200mg tablets', 'Stomach upset, dizziness', 7.50, 150, 'MediGen'),
            ('Amoxicillin', 'Amoxicillin', 'Antibiotic for bacterial infections', '250mg capsules', 'Diarrhea, nausea, skin rash', 12.99, 80, 'AntiBio Labs'),
            ('Lisinopril', 'Lisinopril', 'Blood pressure medication', '10mg tablets', 'Dry cough, dizziness', 15.75, 60, 'CardioMed'),
            ('Metformin', 'Metformin HCl', 'Diabetes medication', '500mg tablets', 'Stomach upset, metallic taste', 18.50, 90, 'DiabetesCare'),
            ('Aspirin', 'Acetylsalicylic acid', 'Blood thinner and pain reliever', '81mg tablets', 'Stomach bleeding, ringing in ears', 4.25, 200, 'GeneralMeds')
        ]
        cursor.executemany('''
            INSERT INTO medications (name, generic_name, description, dosage, side_effects, price, stock_quantity, manufacturer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_medications)
    
    conn.commit()
    conn.close()

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'doctor':
            flash('Access denied. Doctor privileges required.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def patient_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'patient':
            flash('Access denied. Patient privileges required.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        if session['user_type'] == 'doctor':
            return redirect(url_for('doctor_dashboard'))
        else:
            return redirect(url_for('patient_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = sqlite3.connect('hospital.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, password_hash, name, user_type FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['user_name'] = user[2]
            session['user_type'] = user[3]
            
            if user[3] == 'doctor':
                return redirect(url_for('doctor_dashboard'))
            else:
                return redirect(url_for('patient_dashboard'))
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        phone = request.form['phone']
        specialization = request.form.get('specialization', '')
        
        password_hash = generate_password_hash(password)
        
        try:
            conn = sqlite3.connect('hospital.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (name, email, password_hash, user_type, phone, specialization)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, email, password_hash, user_type, phone, specialization))
            conn.commit()
            conn.close()
            
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists')
    
    return render_template('register.html')

@app.route('/patient/dashboard')
@patient_required
def patient_dashboard():
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    
    # Get available doctors
    cursor.execute('SELECT id, name, specialization FROM users WHERE user_type = "doctor"')
    doctors = cursor.fetchall()
    
    # Get patient's appointments
    cursor.execute('''
        SELECT a.id, d.name, a.appointment_date, a.appointment_time, a.status, a.notes
        FROM appointments a
        JOIN users d ON a.doctor_id = d.id
        WHERE a.patient_id = ?
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    ''', (session['user_id'],))
    appointments = cursor.fetchall()
    
    # Get medical records
    cursor.execute('''
        SELECT m.id, d.name, m.diagnosis, m.prescription, m.notes, m.created_at
        FROM medical_records m
        JOIN users d ON m.doctor_id = d.id
        WHERE m.patient_id = ?
        ORDER BY m.created_at DESC
    ''', (session['user_id'],))
    medical_records = cursor.fetchall()
    
    # Get unread notifications count
    cursor.execute('SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0', (session['user_id'],))
    unread_notifications = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template('patient_dashboard.html', 
                         doctors=doctors, 
                         appointments=appointments, 
                         medical_records=medical_records,
                         unread_notifications=unread_notifications)

@app.route('/doctor/dashboard')
@doctor_required
def doctor_dashboard():
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    
    # Get doctor's appointments
    cursor.execute('''
        SELECT a.id, p.name, a.appointment_date, a.appointment_time, a.status, a.notes, p.phone
        FROM appointments a
        JOIN users p ON a.patient_id = p.id
        WHERE a.doctor_id = ?
        ORDER BY a.appointment_date DESC, a.appointment_time DESC
    ''', (session['user_id'],))
    appointments = cursor.fetchall()
    
    # Get doctor's medical records
    cursor.execute('''
        SELECT mr.id, p.name, mr.diagnosis, mr.prescription, mr.notes, mr.created_at, p.phone
        FROM medical_records mr
        JOIN users p ON mr.patient_id = p.id
        WHERE mr.doctor_id = ?
        ORDER BY mr.created_at DESC
    ''', (session['user_id'],))
    medical_records = cursor.fetchall()
    
    conn.close()
    
    return render_template('doctor_dashboard.html', appointments=appointments, medical_records=medical_records)

@app.route('/schedule-appointment', methods=['POST'])
@patient_required
def schedule_appointment():
    doctor_id = request.form['doctor_id']
    appointment_date = request.form['appointment_date']
    appointment_time = request.form['appointment_time']
    notes = request.form['notes']
    
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, notes)
        VALUES (?, ?, ?, ?, ?)
    ''', (session['user_id'], doctor_id, appointment_date, appointment_time, notes))
    conn.commit()
    conn.close()
    
    flash('Appointment scheduled successfully!')
    return redirect(url_for('patient_dashboard'))

@app.route('/doctor/update-appointment', methods=['POST'])
@doctor_required
def update_appointment():
    data = request.get_json()
    appointment_id = data['appointment_id']
    status = data['status']
    
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE appointments SET status = ? WHERE id = ? AND doctor_id = ?
    ''', (status, appointment_id, session['user_id']))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/doctor/medical-record', methods=['POST'])
@doctor_required
def create_medical_record():
    data = request.get_json()
    appointment_id = data['appointment_id']
    diagnosis = data['diagnosis']
    prescription = data['prescription']
    notes = data['notes']
    
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    
    # Get patient_id from appointment
    cursor.execute('SELECT patient_id FROM appointments WHERE id = ? AND doctor_id = ?', 
                   (appointment_id, session['user_id']))
    result = cursor.fetchone()
    
    if result:
        patient_id = result[0]
        cursor.execute('''
            INSERT INTO medical_records (appointment_id, patient_id, doctor_id, diagnosis, prescription, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (appointment_id, patient_id, session['user_id'], diagnosis, prescription, notes))
        conn.commit()
        
    conn.close()
    
    return jsonify({'success': True})

@app.route('/doctor/delete-medical-record/<int:record_id>', methods=['POST'])
@doctor_required
def delete_medical_record(record_id):
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    
    # Get record details before deletion
    cursor.execute('''
        SELECT mr.patient_id, u.name as patient_name, mr.diagnosis, mr.created_at
        FROM medical_records mr
        JOIN users u ON mr.patient_id = u.id
        WHERE mr.id = ? AND mr.doctor_id = ?
    ''', (record_id, session['user_id']))
    record_info = cursor.fetchone()
    
    if record_info:
        patient_id, patient_name, diagnosis, created_at = record_info
        
        # Delete the medical record
        cursor.execute('DELETE FROM medical_records WHERE id = ? AND doctor_id = ?', 
                       (record_id, session['user_id']))
        
        # Create notification for patient
        notification_message = f"Your medical record from {created_at.split()[0]} (Diagnosis: {diagnosis}) has been deleted by Dr. {session['user_name']}"
        cursor.execute('''
            INSERT INTO notifications (user_id, message, type)
            VALUES (?, ?, ?)
        ''', (patient_id, notification_message, 'warning'))
        
        conn.commit()
        success = True
    else:
        success = False
    
    conn.close()
    
    return jsonify({'success': success})

@app.route('/notifications')
@login_required
def get_notifications():
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, message, type, is_read, created_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (session['user_id'],))
    notifications = cursor.fetchall()
    
    conn.close()
    
    return render_template('notifications.html', notifications=notifications)

@app.route('/mark-notification-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE notifications SET is_read = 1 
        WHERE id = ? AND user_id = ?
    ''', (notification_id, session['user_id']))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/departments')
@login_required
def view_departments():
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT d.id, d.name, d.description, d.phone, d.location, u.name as head_doctor
        FROM departments d
        LEFT JOIN users u ON d.head_doctor_id = u.id
        ORDER BY d.name
    ''')
    departments = cursor.fetchall()
    
    # Get doctors for each department
    cursor.execute('''
        SELECT d.id, COUNT(u.id) as doctor_count
        FROM departments d
        LEFT JOIN users u ON u.specialization = d.name AND u.user_type = 'doctor'
        GROUP BY d.id
    ''')
    doctor_counts = dict(cursor.fetchall())
    
    conn.close()
    
    return render_template('departments.html', departments=departments, doctor_counts=doctor_counts)

@app.route('/medications')
@login_required
def view_medications():
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, generic_name, description, dosage, side_effects, price, stock_quantity, manufacturer
        FROM medications
        ORDER BY name
    ''')
    medications = cursor.fetchall()
    
    conn.close()
    
    return render_template('medications.html', medications=medications)

@app.route('/admin/departments', methods=['GET', 'POST'])
@doctor_required
def manage_departments():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        phone = request.form['phone']
        location = request.form['location']
        
        conn = sqlite3.connect('hospital.db')
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO departments (name, description, phone, location)
                VALUES (?, ?, ?, ?)
            ''', (name, description, phone, location))
            conn.commit()
            flash('Department added successfully!')
        except sqlite3.IntegrityError:
            flash('Department name already exists!')
        conn.close()
    
    return redirect(url_for('view_departments'))

@app.route('/admin/medications', methods=['GET', 'POST'])
@doctor_required
def manage_medications():
    if request.method == 'POST':
        name = request.form['name']
        generic_name = request.form['generic_name']
        description = request.form['description']
        dosage = request.form['dosage']
        side_effects = request.form['side_effects']
        price = float(request.form['price'])
        stock_quantity = int(request.form['stock_quantity'])
        manufacturer = request.form['manufacturer']
        
        conn = sqlite3.connect('hospital.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO medications (name, generic_name, description, dosage, side_effects, price, stock_quantity, manufacturer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, generic_name, description, dosage, side_effects, price, stock_quantity, manufacturer))
        conn.commit()
        conn.close()
        
        flash('Medication added successfully!')
    
    return redirect(url_for('view_medications'))

@app.route('/api/medications/search')
@doctor_required
def search_medications():
    query = request.args.get('q', '')
    
    conn = sqlite3.connect('hospital.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name, generic_name, dosage, price
        FROM medications
        WHERE name LIKE ? OR generic_name LIKE ?
        ORDER BY name
        LIMIT 10
    ''', (f'%{query}%', f'%{query}%'))
    medications = cursor.fetchall()
    conn.close()
    
    return jsonify([{
        'id': med[0],
        'name': med[1],
        'generic_name': med[2],
        'dosage': med[3],
        'price': med[4]
    } for med in medications])

def create_templates():
    """Create all template files"""
    
    # Base template
    base_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Hospital Management System{% endblock %}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #0a0a0a;
            color: #fafafa;
            line-height: 1.6;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .nav {
            background: #111;
            padding: 1rem 0;
            border-bottom: 1px solid #333;
            margin-bottom: 2rem;
        }
        
        .nav-content {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .nav h1 {
            color: #fff;
            font-size: 1.5rem;
        }
        
        .nav-links {
            display: flex;
            gap: 1rem;
            align-items: center;
        }
        
        .btn {
            background: #fff;
            color: #000;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-block;
            font-size: 0.9rem;
        }
        
        .btn:hover {
            background: #e6e6e6;
            transform: translateY(-1px);
        }
        
        .btn-secondary {
            background: transparent;
            color: #fff;
            border: 1px solid #333;
        }
        
        .btn-secondary:hover {
            background: #333;
            color: #fff;
        }
        
        .btn-danger {
            background: #dc2626;
            color: #fff;
        }
        
        .btn-danger:hover {
            background: #b91c1c;
        }
        
        .form-container {
            max-width: 400px;
            margin: 2rem auto;
            background: #111;
            padding: 2rem;
            border-radius: 12px;
            border: 1px solid #333;
        }
        
        .form-group {
            margin-bottom: 1rem;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            color: #ccc;
            font-weight: 500;
        }
        
        .form-control {
            width: 100%;
            padding: 0.75rem;
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 8px;
            color: #fff;
            font-size: 1rem;
        }
        
        .form-control:focus {
            outline: none;
            border-color: #666;
            background: #222;
        }
        
        .card {
            background: #111;
            border: 1px solid #333;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1rem;
        }
        
        .card h3 {
            margin-bottom: 1rem;
            color: #fff;
        }
        
        .grid {
            display: grid;
            gap: 1rem;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        }
        
        .alert {
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }
        
        .alert-danger {
            background: #dc2626;
            color: #fff;
        }
        
        .alert-success {
            background: #16a34a;
            color: #fff;
        }
        
        .table {
            width: 100%;
            background: #111;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #333;
        }
        
        .table th,
        .table td {
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid #333;
        }
        
        .table th {
            background: #1a1a1a;
            font-weight: 600;
        }
        
        .status-pending {
            color: #fbbf24;
        }
        
        .status-accepted {
            color: #16a34a;
        }
        
        .status-rejected {
            color: #dc2626;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 1000;
        }
        
        .modal-content {
            background: #111;
            margin: 5% auto;
            padding: 2rem;
            border-radius: 12px;
            max-width: 600px;
            border: 1px solid #333;
        }
        
        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        
        .close:hover {
            color: #fff;
        }
        
        @media (max-width: 768px) {
            .nav-content {
                flex-direction: column;
                gap: 1rem;
            }
            
            .container {
                padding: 10px;
            }
        }
    </style>
</head>
<body>
    {% if session.user_id %}
    <nav class="nav">
        <div class="nav-content">
            <h1>🏥 Hospital Management</h1>
            <div class="nav-links">
                <span>Welcome, {{ session.user_name }}</span>
                <a href="{{ url_for('logout') }}" class="btn btn-secondary">Logout</a>
            </div>
        </div>
    </nav>
    {% endif %}
    
    <div class="container">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alert alert-danger">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </div>
    
    {% block scripts %}{% endblock %}
</body>
</html>'''
    
    # Login template
    login_template = '''{% extends "base.html" %}

{% block content %}
<div class="form-container">
    <h2 style="text-align: center; margin-bottom: 2rem; color: #fff;">Login</h2>
    <form method="POST">
        <div class="form-group">
            <label for="email">Email:</label>
            <input type="email" id="email" name="email" class="form-control" required>
        </div>
        <div class="form-group">
            <label for="password">Password:</label>
            <input type="password" id="password" name="password" class="form-control" required>
        </div>
        <button type="submit" class="btn" style="width: 100%; margin-bottom: 1rem;">Login</button>
    </form>
    <div style="text-align: center;">
        <p style="color: #ccc;">Don't have an account?</p>
        <a href="{{ url_for('register') }}" class="btn btn-secondary">Sign Up</a>
    </div>
</div>
{% endblock %}'''

    # Register template
    register_template = '''{% extends "base.html" %}

{% block content %}
<div class="form-container">
    <h2 style="text-align: center; margin-bottom: 2rem; color: #fff;">Sign Up</h2>
    <form method="POST">
        <div class="form-group">
            <label for="name">Full Name:</label>
            <input type="text" id="name" name="name" class="form-control" required>
        </div>
        <div class="form-group">
            <label for="email">Email:</label>
            <input type="email" id="email" name="email" class="form-control" required>
        </div>
        <div class="form-group">
            <label for="password">Password:</label>
            <input type="password" id="password" name="password" class="form-control" required>
        </div>
        <div class="form-group">
            <label for="phone">Phone:</label>
            <input type="tel" id="phone" name="phone" class="form-control" required>
        </div>
        <div class="form-group">
            <label for="user_type">I am a:</label>
            <select id="user_type" name="user_type" class="form-control" onchange="toggleSpecialization()" required>
                <option value="">Select...</option>
                <option value="patient">Patient</option>
                <option value="doctor">Doctor</option>
            </select>
        </div>
        <div class="form-group" id="specialization-group" style="display: none;">
            <label for="specialization">Specialization:</label>
            <select id="specialization" name="specialization" class="form-control">
                <option value="">Select specialization...</option>
                <option value="Cardiology">Cardiology</option>
                <option value="Neurology">Neurology</option>
                <option value="Orthopedics">Orthopedics</option>
                <option value="Pediatrics">Pediatrics</option>
                <option value="Dermatology">Dermatology</option>
                <option value="General Medicine">General Medicine</option>
            </select>
        </div>
        <button type="submit" class="btn" style="width: 100%; margin-bottom: 1rem;">Sign Up</button>
    </form>
    <div style="text-align: center;">
        <a href="{{ url_for('login') }}" class="btn btn-secondary">Back to Login</a>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
    function toggleSpecialization() {
        const userType = document.getElementById('user_type').value;
        const specializationGroup = document.getElementById('specialization-group');
        const specializationSelect = document.getElementById('specialization');
        
        if (userType === 'doctor') {
            specializationGroup.style.display = 'block';
            specializationSelect.required = true;
        } else {
            specializationGroup.style.display = 'none';
            specializationSelect.required = false;
        }
    }
</script>
{% endblock %}'''

    # Patient dashboard template
    patient_dashboard_template = '''{% extends "base.html" %}

{% block content %}
<h2 style="margin-bottom: 2rem; color: #fff;">Patient Dashboard</h2>

<div style="display: flex; gap: 1rem; margin-bottom: 2rem;">
    <a href="{{ url_for('view_departments') }}" class="btn btn-secondary">🏢 Browse Departments</a>
    <a href="{{ url_for('view_medications') }}" class="btn btn-secondary">💊 Medications</a>
    <a href="{{ url_for('get_notifications') }}" class="btn btn-secondary" style="position: relative;">
        🔔 Notifications
        {% if unread_notifications > 0 %}
        <span style="position: absolute; top: -5px; right: -5px; background: #dc2626; color: white; border-radius: 50%; width: 20px; height: 20px; font-size: 12px; display: flex; align-items: center; justify-content: center;">{{ unread_notifications }}</span>
        {% endif %}
    </a>
</div>

<div class="grid">
    <!-- Schedule Appointment -->
    <div class="card">
        <h3>Schedule New Appointment</h3>
        <form method="POST" action="{{ url_for('schedule_appointment') }}">
            <div class="form-group">
                <label for="doctor_id">Select Doctor:</label>
                <select id="doctor_id" name="doctor_id" class="form-control" required>
                    <option value="">Choose a doctor...</option>
                    {% for doctor in doctors %}
                    <option value="{{ doctor[0] }}">Dr. {{ doctor[1] }} - {{ doctor[2] }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label for="appointment_date">Date:</label>
                <input type="date" id="appointment_date" name="appointment_date" class="form-control" required>
            </div>
            <div class="form-group">
                <label for="appointment_time">Time:</label>
                <select id="appointment_time" name="appointment_time" class="form-control" required>
                    <option value="">Select time...</option>
                    <option value="09:00">09:00 AM</option>
                    <option value="10:00">10:00 AM</option>
                    <option value="11:00">11:00 AM</option>
                    <option value="14:00">02:00 PM</option>
                    <option value="15:00">03:00 PM</option>
                    <option value="16:00">04:00 PM</option>
                </select>
            </div>
            <div class="form-group">
                <label for="notes">Notes (optional):</label>
                <textarea id="notes" name="notes" class="form-control" rows="3" placeholder="Describe your symptoms or reason for visit..."></textarea>
            </div>
            <button type="submit" class="btn">Schedule Appointment</button>
        </form>
    </div>
</div>

<!-- My Appointments -->
<div class="card" style="margin-top: 2rem;">
    <h3>My Appointments</h3>
    {% if appointments %}
    <div style="overflow-x: auto;">
        <table class="table">
            <thead>
                <tr>
                    <th>Doctor</th>
                    <th>Date</th>
                    <th>Time</th>
                    <th>Status</th>
                    <th>Notes</th>
                </tr>
            </thead>
            <tbody>
                {% for appointment in appointments %}
                <tr>
                    <td>Dr. {{ appointment[1] }}</td>
                    <td>{{ appointment[2] }}</td>
                    <td>{{ appointment[3] }}</td>
                    <td><span class="status-{{ appointment[4] }}">{{ appointment[4].title() }}</span></td>
                    <td>{{ appointment[5] or '-' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <p style="color: #ccc;">No appointments scheduled yet.</p>
    {% endif %}
</div>

<!-- Medical Records -->
<div class="card" style="margin-top: 2rem;">
    <h3>Medical Records</h3>
    {% if medical_records %}
    <div style="overflow-x: auto;">
        <table class="table">
            <thead>
                <tr>
                    <th>Doctor</th>
                    <th>Date</th>
                    <th>Diagnosis</th>
                    <th>Prescription</th>
                    <th>Notes</th>
                </tr>
            </thead>
            <tbody>
                {% for record in medical_records %}
                <tr>
                    <td>Dr. {{ record[1] }}</td>
                    <td>{{ record[5].split()[0] }}</td>
                    <td>{{ record[2] or '-' }}</td>
                    <td>{{ record[3] or '-' }}</td>
                    <td>{{ record[4] or '-' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <p style="color: #ccc;">No medical records yet.</p>
    {% endif %}
</div>
{% endblock %}

{% block scripts %}
<script>
    // Set minimum date to today
    document.getElementById('appointment_date').min = new Date().toISOString().split('T')[0];
</script>
{% endblock %}'''

    # Doctor dashboard template
    doctor_dashboard_template = '''{% extends "base.html" %}

{% block content %}
<h2 style="margin-bottom: 2rem; color: #fff;">Doctor Dashboard</h2>

<div style="display: flex; gap: 1rem; margin-bottom: 2rem;">
    <a href="{{ url_for('view_departments') }}" class="btn btn-secondary">🏢 Departments</a>
    <a href="{{ url_for('view_medications') }}" class="btn btn-secondary">💊 Medications</a>
</div>

<!-- Pending Appointments -->
<div class="card">
    <h3>Patient Appointments</h3>
    {% if appointments %}
    <div style="overflow-x: auto;">
        <table class="table">
            <thead>
                <tr>
                    <th>Patient</th>
                    <th>Phone</th>
                    <th>Date</th>
                    <th>Time</th>
                    <th>Status</th>
                    <th>Notes</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for appointment in appointments %}
                <tr>
                    <td>{{ appointment[1] }}</td>
                    <td>{{ appointment[6] }}</td>
                    <td>{{ appointment[2] }}</td>
                    <td>{{ appointment[3] }}</td>
                    <td><span class="status-{{ appointment[4] }}">{{ appointment[4].title() }}</span></td>
                    <td>{{ appointment[5] or '-' }}</td>
                    <td>
                        {% if appointment[4] == 'pending' %}
                        <button onclick="updateAppointment({{ appointment[0] }}, 'accepted')" class="btn" style="margin-right: 0.5rem; padding: 0.5rem;">Accept</button>
                        <button onclick="updateAppointment({{ appointment[0] }}, 'rejected')" class="btn btn-danger" style="padding: 0.5rem;">Reject</button>
                        {% elif appointment[4] == 'accepted' %}
                        <button onclick="openMedicalRecord({{ appointment[0] }}, '{{ appointment[1] }}')" class="btn" style="padding: 0.5rem;">Medical Record</button>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <p style="color: #ccc;">No appointments yet.</p>
    {% endif %}
</div>

<!-- Medical Record Modal -->
<div id="medicalRecordModal" class="modal">
    <div class="modal-content">
        <span class="close" onclick="closeMedicalRecord()">&times;</span>
        <h3 id="modalTitle">Medical Record</h3>
        <form id="medicalRecordForm">
            <input type="hidden" id="appointmentId" name="appointment_id">
            <div class="form-group">
                <label for="diagnosis">Diagnosis:</label>
                <textarea id="diagnosis" name="diagnosis" class="form-control" rows="3" required></textarea>
            </div>
            <div class="form-group">
                <label for="prescription">Prescription:</label>
                <div style="position: relative;">
                    <input type="text" id="medicationSearch" class="form-control" placeholder="Search medications..." autocomplete="off">
                    <div id="medicationResults" style="position: absolute; top: 100%; left: 0; right: 0; background: #222; border: 1px solid #333; border-radius: 8px; max-height: 200px; overflow-y: auto; z-index: 1001; display: none;"></div>
                </div>
                <textarea id="prescription" name="prescription" class="form-control" rows="3" style="margin-top: 0.5rem;" placeholder="Selected medications will appear here..."></textarea>
            </div>
            <div class="form-group">
                <label for="medical_notes">Notes:</label>
                <textarea id="medical_notes" name="notes" class="form-control" rows="3"></textarea>
            </div>
            <button type="submit" class="btn">Save Medical Record</button>
        </form>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
    let selectedMedications = [];
    
    function updateAppointment(appointmentId, status) {
        fetch('/doctor/update-appointment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                appointment_id: appointmentId,
                status: status
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Error updating appointment');
            }
        });
    }
    
    function openMedicalRecord(appointmentId, patientName) {
        document.getElementById('appointmentId').value = appointmentId;
        document.getElementById('modalTitle').textContent = 'Medical Record for ' + patientName;
        document.getElementById('medicalRecordModal').style.display = 'block';
        selectedMedications = [];
        updatePrescriptionDisplay();
    }
    
    function closeMedicalRecord() {
        document.getElementById('medicalRecordModal').style.display = 'none';
        document.getElementById('medicationResults').style.display = 'none';
    }
    
    // Medication search functionality
    document.getElementById('medicationSearch').addEventListener('input', function(e) {
        const query = e.target.value.trim();
        if (query.length < 2) {
            document.getElementById('medicationResults').style.display = 'none';
            return;
        }
        
        fetch(`/api/medications/search?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(medications => {
                const resultsDiv = document.getElementById('medicationResults');
                resultsDiv.innerHTML = '';
                
                if (medications.length > 0) {
                    medications.forEach(med => {
                        const div = document.createElement('div');
                        div.style.cssText = 'padding: 0.75rem; cursor: pointer; border-bottom: 1px solid #333;';
                        div.innerHTML = `
                            <strong>${med.name}</strong> (${med.generic_name})<br>
                            <small style="color: #ccc;">${med.dosage} - ${med.price}</small>
                        `;
                        div.addEventListener('click', () => addMedication(med));
                        div.addEventListener('mouseenter', () => div.style.background = '#333');
                        div.addEventListener('mouseleave', () => div.style.background = 'transparent');
                        resultsDiv.appendChild(div);
                    });
                    resultsDiv.style.display = 'block';
                } else {
                    resultsDiv.style.display = 'none';
                }
            });
    });
    
    function addMedication(medication) {
        // Check if medication already selected
        if (!selectedMedications.find(med => med.id === medication.id)) {
            selectedMedications.push(medication);
            updatePrescriptionDisplay();
        }
        document.getElementById('medicationSearch').value = '';
        document.getElementById('medicationResults').style.display = 'none';
    }
    
    function updatePrescriptionDisplay() {
        const prescriptionText = selectedMedications.map(med => 
            `${med.name} (${med.generic_name}) - ${med.dosage}`
        ).join('\\n');
        document.getElementById('prescription').value = prescriptionText;
    }
    
    function removeMedication(index) {
        selectedMedications.splice(index, 1);
        updatePrescriptionDisplay();
    }
    
    document.getElementById('medicalRecordForm').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        const data = Object.fromEntries(formData);
        
        fetch('/doctor/medical-record', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Medical record saved successfully');
                closeMedicalRecord();
                location.reload();
            } else {
                alert('Error saving medical record');
            }
        });
    });
    
    // Close modal when clicking outside
    window.onclick = function(event) {
        const modal = document.getElementById('medicalRecordModal');
        if (event.target == modal) {
            closeMedicalRecord();
        }
    }
    
    // Hide medication results when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('#medicationSearch') && !e.target.closest('#medicationResults')) {
            document.getElementById('medicationResults').style.display = 'none';
        }
    });
</script>
{% endblock %}'''
    
    # Write template files with UTF-8 encoding
    with open('templates/base.html', 'w', encoding='utf-8') as f:
        f.write(base_template)
    
    with open('templates/login.html', 'w', encoding='utf-8') as f:
        f.write(login_template)
    
    with open('templates/register.html', 'w', encoding='utf-8') as f:
        f.write(register_template)
    
    with open('templates/patient_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(patient_dashboard_template)
    
    with open('templates/doctor_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(doctor_dashboard_template)
    
    # Departments template
    departments_template = '''{% extends "base.html" %}

{% block content %}
<h2 style="margin-bottom: 2rem; color: #fff;">Hospital Departments</h2>

{% if session.user_type == 'doctor' %}
<div class="card" style="margin-bottom: 2rem;">
    <h3>Add New Department</h3>
    <form method="POST" action="{{ url_for('manage_departments') }}">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="form-group">
                <label for="name">Department Name:</label>
                <input type="text" id="name" name="name" class="form-control" required>
            </div>
            <div class="form-group">
                <label for="phone">Phone:</label>
                <input type="tel" id="phone" name="phone" class="form-control" required>
            </div>
        </div>
        <div class="form-group">
            <label for="description">Description:</label>
            <textarea id="description" name="description" class="form-control" rows="2" required></textarea>
        </div>
        <div class="form-group">
            <label for="location">Location:</label>
            <input type="text" id="location" name="location" class="form-control" required>
        </div>
        <button type="submit" class="btn">Add Department</button>
    </form>
</div>
{% endif %}

<div class="grid">
    {% for department in departments %}
    <div class="card">
        <h3 style="color: #fff; margin-bottom: 0.5rem;">{{ department[1] }}</h3>
        <p style="color: #ccc; margin-bottom: 1rem;">{{ department[2] }}</p>
        
        <div style="margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                <span style="color: #aaa;">📍 Location:</span>
                <span>{{ department[4] }}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                <span style="color: #aaa;">📞 Phone:</span>
                <span>{{ department[3] }}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                <span style="color: #aaa;">👨‍⚕️ Doctors:</span>
                <span>{{ doctor_counts.get(department[0], 0) }}</span>
            </div>
            {% if department[5] %}
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #aaa;">🏥 Head:</span>
                <span>Dr. {{ department[5] }}</span>
            </div>
            {% endif %}
        </div>
        
        {% if session.user_type == 'patient' %}
        <a href="{{ url_for('patient_dashboard') }}" class="btn" style="width: 100%;">Book Appointment</a>
        {% endif %}
    </div>
    {% endfor %}
</div>
{% endblock %}'''
    
    # Medications template
    medications_template = '''{% extends "base.html" %}

{% block content %}
<h2 style="margin-bottom: 2rem; color: #fff;">Hospital Medications</h2>

{% if session.user_type == 'doctor' %}
<div class="card" style="margin-bottom: 2rem;">
    <h3>Add New Medication</h3>
    <form method="POST" action="{{ url_for('manage_medications') }}">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="form-group">
                <label for="name">Brand Name:</label>
                <input type="text" id="name" name="name" class="form-control" required>
            </div>
            <div class="form-group">
                <label for="generic_name">Generic Name:</label>
                <input type="text" id="generic_name" name="generic_name" class="form-control" required>
            </div>
        </div>
        <div class="form-group">
            <label for="description">Description:</label>
            <textarea id="description" name="description" class="form-control" rows="2" required></textarea>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem;">
            <div class="form-group">
                <label for="dosage">Dosage:</label>
                <input type="text" id="dosage" name="dosage" class="form-control" required>
            </div>
            <div class="form-group">
                <label for="price">Price ($):</label>
                <input type="number" step="0.01" id="price" name="price" class="form-control" required>
            </div>
            <div class="form-group">
                <label for="stock_quantity">Stock Quantity:</label>
                <input type="number" id="stock_quantity" name="stock_quantity" class="form-control" required>
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="form-group">
                <label for="manufacturer">Manufacturer:</label>
                <input type="text" id="manufacturer" name="manufacturer" class="form-control" required>
            </div>
            <div class="form-group">
                <label for="side_effects">Side Effects:</label>
                <input type="text" id="side_effects" name="side_effects" class="form-control">
            </div>
        </div>
        <button type="submit" class="btn">Add Medication</button>
    </form>
</div>
{% endif %}

<div class="card">
    <h3>Available Medications</h3>
    <div style="margin-bottom: 1rem;">
        <input type="text" id="searchMedications" class="form-control" placeholder="Search medications by name or generic name...">
    </div>
    
    {% if medications %}
    <div style="overflow-x: auto;">
        <table class="table" id="medicationsTable">
            <thead>
                <tr>
                    <th>Brand Name</th>
                    <th>Generic Name</th>
                    <th>Description</th>
                    <th>Dosage</th>
                    <th>Price</th>
                    <th>Stock</th>
                    <th>Manufacturer</th>
                    {% if session.user_type == 'doctor' %}
                    <th>Side Effects</th>
                    {% endif %}
                </tr>
            </thead>
            <tbody>
                {% for medication in medications %}
                <tr>
                    <td><strong>{{ medication[1] }}</strong></td>
                    <td>{{ medication[2] }}</td>
                    <td>{{ medication[3] }}</td>
                    <td>{{ medication[4] }}</td>
                    <td>${{ "%.2f"|format(medication[6]) }}</td>
                    <td>
                        <span style="color: {% if medication[7] > 50 %}#16a34a{% elif medication[7] > 10 %}#fbbf24{% else %}#dc2626{% endif %}">
                            {{ medication[7] }}
                        </span>
                    </td>
                    <td>{{ medication[8] }}</td>
                    {% if session.user_type == 'doctor' %}
                    <td style="font-size: 0.9rem; color: #ccc;">{{ medication[5] or '-' }}</td>
                    {% endif %}
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <p style="color: #ccc;">No medications available.</p>
    {% endif %}
</div>
{% endblock %}

{% block scripts %}
<script>
    // Search functionality
    document.getElementById('searchMedications').addEventListener('input', function(e) {
        const searchTerm = e.target.value.toLowerCase();
        const table = document.getElementById('medicationsTable');
        const rows = table.getElementsByTagName('tr');
        
        for (let i = 1; i < rows.length; i++) {
            const row = rows[i];
            const brandName = row.cells[0].textContent.toLowerCase();
            const genericName = row.cells[1].textContent.toLowerCase();
            
            if (brandName.includes(searchTerm) || genericName.includes(searchTerm)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        }
    });
</script>
{% endblock %}'''
    
    with open('templates/departments.html', 'w', encoding='utf-8') as f:
        f.write(departments_template)
    
    with open('templates/medications.html', 'w', encoding='utf-8') as f:
        f.write(medications_template)
    
    # Notifications template
    notifications_template = '''{% extends "base.html" %}

{% block content %}
<h2 style="margin-bottom: 2rem; color: #fff;">Notifications</h2>

<div style="margin-bottom: 2rem;">
    <a href="{{ url_for('patient_dashboard') }}" class="btn btn-secondary">← Back to Dashboard</a>
</div>

<div class="card">
    <h3>Your Notifications</h3>
    {% if notifications %}
    <div style="space-y: 1rem;">
        {% for notification in notifications %}
        <div class="alert alert-{{ notification[2] }}" style="position: relative; margin-bottom: 1rem; padding-right: 3rem;">
            <div style="margin-bottom: 0.5rem;">
                <strong>{{ notification[1] }}</strong>
            </div>
            <div style="font-size: 0.9rem; color: #ccc;">
                {{ notification[4] }}
            </div>
            {% if notification[3] == 0 %}
            <button onclick="markAsRead({{ notification[0] }})" 
                    style="position: absolute; top: 0.5rem; right: 0.5rem; background: none; border: none; color: #ccc; cursor: pointer; font-size: 1.2rem;"
                    title="Mark as read">
                ✕
            </button>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    {% else %}
    <p style="color: #ccc;">No notifications yet.</p>
    {% endif %}
</div>
{% endblock %}

{% block scripts %}
<script>
    function markAsRead(notificationId) {
        fetch(`/mark-notification-read/${notificationId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            }
        });
    }
</script>
{% endblock %}'''
    
    with open('templates/notifications.html', 'w', encoding='utf-8') as f:
        f.write(notifications_template)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Create template files
    create_templates()
    
    init_db()
    app.run(debug=True)