import os
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from twilio.rest import Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key")
DATABASE = "database.db"

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Email Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Initialize Database
def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            med_name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            time TEXT NOT NULL,
            caretaker_phone TEXT,
            caretaker_email TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            med_id INTEGER,
            sent_time TEXT,
            FOREIGN KEY(med_id) REFERENCES medications(id)
        )''')
        conn.commit()

init_db()

# Helper: Send SMS
def send_sms(phone, message):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(body=message, from_=TWILIO_PHONE_NUMBER, to=phone)
    except Exception as e:
        print(f"Error sending SMS: {e}")

# Helper: Send Email
def send_email(to_email, subject, message):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Error sending email: {e}")

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                # User already registered
                return render_template("register.html", error="Dear user, you are already registered. Please log in.")
            
            cursor.execute("INSERT INTO users (name, phone, email, password) VALUES (?, ?, ?, ?)",
                           (name, phone, email, password))
            conn.commit()
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user[4], password):
                session["user_id"] = user[0]
                return redirect(url_for("dashboard"))
            else:
                # Pass the error message to the template
                return render_template("login.html", error="Please enter the correct password.")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    medications = []

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, med_name, dosage, time, caretaker_phone, caretaker_email 
            FROM medications 
            WHERE user_id = ?
        """, (user_id,))
        medications = cursor.fetchall()

    return render_template("dashboard.html", medications=medications)

@app.route("/schedule", methods=["GET", "POST"])
def schedule():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        med_name = request.form["med_name"]
        dosage = request.form["dosage"]
        time = request.form["time"]
        caretaker_phone = request.form["caretaker_phone"]
        caretaker_email = request.form["caretaker_email"]

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO medications (user_id, med_name, dosage, time, caretaker_phone, caretaker_email)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session["user_id"], med_name, dosage, time, caretaker_phone, caretaker_email))
            conn.commit()

        # Send notifications
        send_sms(caretaker_phone, f"Your ward has a reminder: {med_name} (Dosage: {dosage}) at {time}.")
        send_email(caretaker_email, "Ward's Medication Reminder", f"Reminder: {med_name} (Dosage: {dosage}) at {time}.")
        
        # Pop-up confirmation
        return render_template("success.html", message="You have successfully scheduled your medication.")

    return render_template("schedule.html")

@app.route("/delete_medication/<int:med_id>", methods=["POST"])
def delete_medication(med_id):
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        
        # Delete the medication from the 'medications' table using the med_id
        cursor.execute("DELETE FROM medications WHERE id = ?", (med_id,))
        conn.commit()
        
        # Optionally, you can also remove any notifications related to this medication
        cursor.execute("DELETE FROM notifications WHERE med_id = ?", (med_id,))
        conn.commit()

    return redirect(url_for('dashboard'))  # Redirect back to the dashboard page

@app.route("/logout")
def logout():
    session.clear()  # Clear all session data
    return redirect(url_for("login"))  # Redirect to login page

@app.route("/send_reminders")
def send_reminders():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT medications.id, med_name, dosage, time, phone, email, caretaker_phone, caretaker_email 
            FROM medications 
            INNER JOIN users ON medications.user_id = users.id
        """)
        schedules = cursor.fetchall()

        for schedule in schedules:
            med_id, med_name, dosage, time, phone, email, caretaker_phone, caretaker_email = schedule
            message = f"Reminder: Take your medication '{med_name}' (Dosage: {dosage}) at {time}."

            # Check if notification was already sent
            cursor.execute("SELECT * FROM notifications WHERE med_id = ? AND sent_time = ?", (med_id, time))
            if cursor.fetchone():
                continue

            # Send SMS and Email
            send_sms(phone, message)  # User
            send_sms(caretaker_phone, f"Your ward has a reminder: {message}")  # Caretaker

            send_email(email, "Medication Reminder", message)  # User
            send_email(caretaker_email, "Ward's Medication Reminder", f"Your ward: {message}")  # Caretaker

            # Log notification
            cursor.execute("INSERT INTO notifications (med_id, sent_time) VALUES (?, ?)", (med_id, time))
        conn.commit()

    return "Reminders sent successfully!"

# Scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=send_reminders, trigger="interval", minutes=1)  # Adjust as needed
scheduler.start()

if __name__ == "__main__":
    app.run(debug=True)
