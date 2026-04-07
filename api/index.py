# api/index.py
import os
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import cv2
import numpy as np
import face_recognition
import base64
import math

# Load local .env if it exists
load_dotenv()

# IMPORTANT: For Vercel, point to the root templates folder
app = Flask(__name__, template_folder='../templates')
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# ==============================
# 🔹 Database Configuration
# ==============================
def get_db_connection():
    """Helper to get a fresh connection for every request (best for serverless)."""
    return mysql.connector.connect(
        host=os.environ.get('MYSQL_HOST', 'localhost'),
        user=os.environ.get('MYSQL_USER', 'root'),
        password=os.environ.get('MYSQL_PASSWORD', ''),
        database=os.environ.get('MYSQL_DB', 'tracker'),
        port=int(os.environ.get('MYSQL_PORT', 3306)),
        # Standard SSL for TiDB Serverless
        ssl_disabled=False
    )

# ==============================
# 🔹 SIGNUP
# ==============================
@app.route("/", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        roll_no = request.form.get("rollno")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role", "student")
        department = request.form.get("department")
        div = request.form.get("div")

        image = request.files.get("profile_image")
        if not image or image.filename == "":
            return "Please upload a profile image"

        hashed_password = generate_password_hash(password)
        image_data = image.read()
        image_np = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)

        if img is None:
            return "Invalid image"

        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb_img)

        if len(encodings) == 0:
            return "No face detected"

        face_encoding = encodings[0]
        encoding_string = np.array2string(face_encoding)

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return "User already exists"

        cur.execute("SELECT face_encoding FROM users WHERE face_encoding IS NOT NULL")
        existing_faces = cur.fetchall()
        for face in existing_faces:
            stored_encoding_str = face[0]
            if stored_encoding_str:
                stored_encoding = np.fromstring(stored_encoding_str.strip('[]'), sep=' ')
                distance = face_recognition.face_distance([stored_encoding], face_encoding)
                if distance[0] < 0.5:
                    cur.close()
                    conn.close()
                    return "<script>alert('You have already signed up, please do login. or invalid photo'); window.location.href='/login';</script>"

        cur.execute("""
            INSERT INTO users 
            (name, roll_no, email, password, profile_image, face_encoding, role, department, Division)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (name, roll_no, email, hashed_password, image_data, encoding_string, role, department, div))

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for("login"))

    return render_template("sign)up.html")

# ==============================
# 🔹 LOGIN (PASSWORD ONLY)
# ==============================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        if not email or not password:
            return "Email or Password missing!"

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, roll_no, email, password, role FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if not user:
            cur.close()
            conn.close()
            return "User not found"

        if not check_password_hash(user[4], password):
            cur.close()
            conn.close()
            return "Invalid Email or Password!"
        
        if user[5] != role:
            cur.close()
            conn.close()
            return "Please enter the correct role for it"

        session["user"] = user[1]
        session["role"] = user[5] if len(user) > 5 else "student"
        cur.close()
        conn.close()
        return redirect(url_for("dashboard"))

    return render_template("login.html")

# ==============================
# 🔹 DASHBOARD
# ==============================
@app.route("/dashboard")
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()

    if "user" in session:
        role = session.get("role", "student")
        if role == "teacher":
            cur.execute("SELECT noncance FROM users WHERE name=%s", (session["user"],))
            result = cur.fetchone()
            teacher_nonce = result[0] if result and result[0] else None
            cur.close()
            conn.close()
            return render_template("teacher.html", user=session["user"], teacher_nonce=teacher_nonce)
        elif role == "student":
            cur.close()
            conn.close()
            return render_template("student.html", user=session["user"])

    cur.execute("SELECT Ttotal_student FROM users WHERE role='teacher' AND Ttotal_student IS NOT NULL ORDER BY id DESC LIMIT 1")
    result = cur.fetchone()
    total_students = result[0] if result else 0
    cur.close()
    conn.close()
    return render_template("index.html", total_students=total_students)

# ==============================
# 🔹 capture the live image 
# ==============================
@app.route("/recognize_face", methods=["POST"])
def recognize_face():
    data = request.get_json()
    image_data = data["image"]
    image_data = image_data.split(",")[1]
    image_bytes = base64.b64decode(image_data)

    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img is None:
        return "Invalid Image"

    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    encodings = face_recognition.face_encodings(rgb_img)

    if len(encodings) == 0:
        return "No Face Detected ❌"

    live_encoding = encodings[0]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, roll_no, face_encoding, department, Division FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()

    for user in users:
        name, roll_no, encoding_string, department, div = user[0], user[1], user[2], user[3], user[4]
        if encoding_string is None: continue
        stored_encoding = np.fromstring(encoding_string.strip('[]'), sep=' ')
        distance = face_recognition.face_distance([stored_encoding], live_encoding)
        if distance[0] < 0.5:
            return f"{name}|{roll_no}|{department}|{div}"

    return "Face Not Matched ❌"

# ==============================
# 🔹 LOGOUT
# ==============================
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# ==============================
# 🔹 live locatio fetching into the database 
# ==============================
@app.route("/save_teacher_location", methods=["POST"])
def save_teacher_location():
    if "user" not in session:
        return redirect(url_for("login"))

    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")
    total_students = request.form.get("total_students")
    new_nonce = request.form.get("nonce_code")

    if not new_nonce:
        import random
        new_nonce = str(random.randint(10000, 99999))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users 
        SET Tlive_lat=%s, Tlive_lng=%s, Ttotal_student=%s, noncance=%s 
        WHERE name=%s
    """, (latitude, longitude, total_students, new_nonce, session["user"]))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("dashboard"))

# ==============================
# 🔹 STUDENT VERIFY POST
# ==============================
@app.route("/student_verify", methods=["POST"])
def student_verify():
    if "user" not in session or session.get("role") != "student":
        return redirect(url_for("login"))
    
    student_lat = request.form.get("latitude")
    student_lng = request.form.get("longitude")
    student_code = request.form.get("nonce_code")

    if not student_lat or not student_lng or not student_code:
        return "<script>alert('Missing location or code!'); window.location.href='/dashboard';</script>"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT Tlive_lat, Tlive_lng, noncance FROM users WHERE role='teacher' AND noncance IS NOT NULL AND noncance != '0' AND noncance != '' ORDER BY id DESC LIMIT 1")
    teacher_loc = cur.fetchone()
    cur.close()
    conn.close()

    if not teacher_loc:
        return "<script>alert('Teacher hasn\\'t set location or code yet.'); window.location.href='/dashboard';</script>"
    
    t_lat, t_lng, t_nonce = teacher_loc[0], teacher_loc[1], teacher_loc[2]

    if str(student_code).strip().upper() != str(t_nonce).strip().upper():
        return "<script>alert('Incorrect Code! ❌'); window.location.href='/dashboard';</script>"
    
    def calculate_distance(lat1, lon1, lat2, lon2):
        if not lat1 or not lon1 or not lat2 or not lon2: return 999999
        try:
            R = 6371e3
            radLat1, radLat2 = math.radians(float(lat1)), math.radians(float(lat2))
            deltaLat, deltaLon = math.radians(float(lat2)-float(lat1)), math.radians(float(lon2)-float(lon1))
            a = math.sin(deltaLat/2)**2 + math.cos(radLat1)*math.cos(radLat2)*math.sin(deltaLon/2)**2
            return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))
        except: return 999999

    dist = calculate_distance(student_lat, student_lng, t_lat, t_lng)
    if dist > 106.68:  # 350 ft
        return f"<script>alert('You are too far away from the teacher!'); window.location.href='/dashboard';</script>"
    
    return redirect(url_for("dashboardd"))

# ==============================
# 🔹 for student connection if location is successfull 
# ==============================
@app.route("/dashboardd")
def dashboardd():
    if "user" not in session or session.get("role") != "student":
        return redirect(url_for("login"))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT Ttotal_student FROM users WHERE role='teacher' AND Ttotal_student IS NOT NULL ORDER BY id DESC LIMIT 1")
    result = cur.fetchone()
    cur.close()
    conn.close()
    total_students = result[0] if result else 0
    return render_template("index.html", user=session["user"], total_students=total_students)

# Vercel needs the app object
app = app
