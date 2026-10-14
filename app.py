import os
import sqlite3
import pickle
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================
# Flask configuration
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")
MODEL_PATH = os.path.join(BASE_DIR, "stress_model.pkl")

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SLEEPSENSE_SECRET_KEY",
    "CHANGE-THIS-SECRET-KEY-BEFORE-DEPLOYMENT"
)


# ============================================================
# Database helpers
# ============================================================

def get_db_connection():
    """Return a SQLite connection whose rows can be accessed by column name."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """Compatibility alias for any older route that calls get_db()."""
    return get_db_connection()


def ensure_column(conn, table, column, definition):
    """Add a column to an existing table only when it is missing."""
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_database():
    """
    Create the tables needed by this application and add created_at to an
    existing predictions table if it does not already exist.
    This does not delete existing records.
    """
    conn = get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                heart_rate REAL,
                respiratory_rate REAL,
                body_temperature REAL,
                blood_oxygen REAL,
                sleep_hours REAL,
                emotional_state REAL,
                lifestyle_score REAL,
                stress_level TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS family_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                contact_name TEXT NOT NULL,
                relationship TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_read INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        """)

        # Add fields to older databases without deleting their data.
        ensure_column(conn, "users", "age", "INTEGER")
        ensure_column(conn, "users", "gender", "TEXT")
        ensure_column(conn, "users", "created_at", "TEXT")
        ensure_column(conn, "predictions", "user_id", "INTEGER")
        ensure_column(conn, "predictions", "heart_rate", "REAL")
        ensure_column(conn, "predictions", "respiratory_rate", "REAL")
        ensure_column(conn, "predictions", "body_temperature", "REAL")
        ensure_column(conn, "predictions", "blood_oxygen", "REAL")
        ensure_column(conn, "predictions", "sleep_hours", "REAL")
        ensure_column(conn, "predictions", "emotional_state", "REAL")
        ensure_column(conn, "predictions", "lifestyle_score", "REAL")
        ensure_column(conn, "predictions", "stress_level", "TEXT")
        ensure_column(conn, "predictions", "created_at", "TEXT")

        conn.commit()
    finally:
        conn.close()


# Initialize the database whenever the application starts.
init_database()


# ============================================================
# Load the machine-learning model (if available)
# ============================================================

model = None
try:
    with open(MODEL_PATH, "rb") as model_file:
        model = pickle.load(model_file)
except (FileNotFoundError, pickle.UnpicklingError, EOFError, OSError):
    model = None


# ============================================================
# Authentication helpers
# ============================================================

def login_required():
    return "user_id" in session


def admin_required():
    return bool(session.get("admin_logged_in"))


def get_stress_prediction(
    heart_rate, respiratory_rate, body_temperature,
    blood_oxygen, sleep_hours, emotional_state, lifestyle_score
):
    """
    Use the saved model only when its expected feature count matches the
    seven inputs supplied by this app. Otherwise use a simple demonstration
    rule-based score. This is a student-project demo, not a medical diagnosis.
    """
    features = [
        heart_rate,
        respiratory_rate,
        body_temperature,
        blood_oxygen,
        sleep_hours,
        emotional_state,
        lifestyle_score
    ]

    if model is not None:
        try:
            expected = getattr(model, "n_features_in_", len(features))
            if expected == len(features):
                return str(model.predict([features])[0])
        except (ValueError, TypeError, AttributeError):
            pass

    score = 0
    if heart_rate > 90:
        score += 1
    if respiratory_rate > 20:
        score += 1
    # Body temperature is entered in Celsius in this application.
    if body_temperature > 37.5:
        score += 1
    if blood_oxygen < 95:
        score += 1
    if sleep_hours < 6:
        score += 1
    if emotional_state > 7:
        score += 1
    if lifestyle_score < 5:
        score += 1

    if score <= 2:
        return "Low"
    if score <= 4:
        return "Moderate"
    return "High"


def create_notification(user_id, message):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
            (user_id, message)
        )
        conn.commit()
    finally:
        conn.close()


# ============================================================
# Home
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


# ============================================================
# Register
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("fullname", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        age_text = request.form.get("age", "").strip()
        gender = request.form.get("gender", "").strip()

        if not name or not email or not password:
            flash("Please complete all required fields.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("register"))

        try:
            age = int(age_text) if age_text else None
            if age is not None and not 1 <= age <= 120:
                raise ValueError
        except ValueError:
            flash("Please enter a valid age.", "error")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO users (name, email, password, age, gender)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, email, password_hash, age, gender or None)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            flash("This email is already registered. Please log in.", "warning")
            return redirect(url_for("register"))
        finally:
            conn.close()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# ============================================================
# Login
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()
        try:
            user = conn.execute(
                "SELECT * FROM users WHERE LOWER(email) = ?",
                (email,)
            ).fetchone()
        finally:
            conn.close()

        # Existing old accounts may contain plain-text passwords from an
        # earlier version. Accept them once, then upgrade them to a hash.
        password_ok = False
        if user:
            stored_password = user["password"] or ""
            try:
                password_ok = check_password_hash(stored_password, password)
            except (ValueError, TypeError):
                password_ok = False

            if not password_ok and stored_password == password:
                password_ok = True
                new_hash = generate_password_hash(password)
                update_conn = get_db_connection()
                try:
                    update_conn.execute(
                        "UPDATE users SET password = ? WHERE id = ?",
                        (new_hash, user["id"])
                    )
                    update_conn.commit()
                finally:
                    update_conn.close()

        if password_ok:
            session.clear()
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            session["name"] = user["name"]
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


# ============================================================
# Dashboard
# ============================================================

@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db_connection()

    try:
        total_predictions = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE user_id = ?",
            (user_id,)
        ).fetchone()[0]

        avg_result = conn.execute(
            "SELECT AVG(sleep_hours) FROM predictions WHERE user_id = ?",
            (user_id,)
        ).fetchone()[0]
        avg_sleep = round(avg_result, 2) if avg_result is not None else None

        latest_row = conn.execute(
            """
            SELECT stress_level FROM predictions
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (user_id,)
        ).fetchone()
        latest_stress = latest_row["stress_level"] if latest_row else None

        sleep_rows = conn.execute(
            """
            SELECT DATE(created_at) AS sleep_date,
                   AVG(sleep_hours) AS avg_sleep
            FROM predictions
            WHERE user_id = ?
              AND created_at IS NOT NULL
              AND sleep_hours IS NOT NULL
            GROUP BY DATE(created_at)
            ORDER BY sleep_date DESC
            LIMIT 7
            """,
            (user_id,)
        ).fetchall()
        sleep_rows = list(reversed(sleep_rows))

        sleep_labels = [row["sleep_date"] for row in sleep_rows]
        sleep_values = [
            round(row["avg_sleep"], 2) for row in sleep_rows
        ]

        stress_counts = {"Low": 0, "Moderate": 0, "High": 0}
        stress_rows = conn.execute(
            """
            SELECT stress_level, COUNT(*) AS total
            FROM predictions
            WHERE user_id = ?
            GROUP BY stress_level
            """,
            (user_id,)
        ).fetchall()

        for row in stress_rows:
            level = row["stress_level"]
            if level in stress_counts:
                stress_counts[level] = row["total"]

        return render_template(
            "dashboard.html",
            name=session.get("name", "User"),
            total_predictions=total_predictions,
            avg_sleep=avg_sleep,
            latest_stress=latest_stress,
            sleep_labels=sleep_labels,
            sleep_values=sleep_values,
            stress_counts=stress_counts
        )
    finally:
        conn.close()


# ============================================================
# Logout
# ============================================================

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ============================================================
# Predict stress
# ============================================================

@app.route("/predict", methods=["GET", "POST"])
def predict():
    if not login_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            heart_rate = float(request.form["heart_rate"])
            respiratory_rate = float(
                request.form.get("respiratory_rate",
                                 request.form.get("respiration_rate", ""))
            )
            body_temperature = float(
                request.form.get("body_temperature",
                                 request.form.get("body_temp", ""))
            )
            blood_oxygen = float(request.form["blood_oxygen"])
            sleep_hours = float(request.form["sleep_hours"])
            emotional_state = float(request.form.get("emotional_state", 5))
            lifestyle_score = float(request.form.get("lifestyle_score", 5))
        except (KeyError, ValueError):
            flash("Please enter valid numbers in all prediction fields.", "error")
            return redirect(url_for("predict"))

        if not (30 <= heart_rate <= 220):
            flash("Heart rate must be between 30 and 220 bpm.", "error")
            return redirect(url_for("predict"))
        if not (5 <= respiratory_rate <= 60):
            flash("Respiration rate must be between 5 and 60 breaths/min.", "error")
            return redirect(url_for("predict"))
        if not (30 <= body_temperature <= 45):
            flash("Enter body temperature in Celsius (30–45).", "error")
            return redirect(url_for("predict"))
        if not (0 <= blood_oxygen <= 100):
            flash("Blood oxygen must be between 0 and 100 percent.", "error")
            return redirect(url_for("predict"))
        if not (0 <= sleep_hours <= 24):
            flash("Sleep hours must be between 0 and 24.", "error")
            return redirect(url_for("predict"))
        if not (0 <= emotional_state <= 10 and 0 <= lifestyle_score <= 10):
            flash("Emotional state and lifestyle score must be from 0 to 10.", "error")
            return redirect(url_for("predict"))

        stress = get_stress_prediction(
            heart_rate, respiratory_rate, body_temperature,
            blood_oxygen, sleep_hours, emotional_state, lifestyle_score
        )

        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO predictions (
                    user_id, heart_rate, respiratory_rate, body_temperature,
                    blood_oxygen, sleep_hours, emotional_state,
                    lifestyle_score, stress_level, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"], heart_rate, respiratory_rate,
                    body_temperature, blood_oxygen, sleep_hours,
                    emotional_state, lifestyle_score, stress,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )
            conn.commit()
        finally:
            conn.close()

        create_notification(
            session["user_id"],
            f"Your latest stress prediction is {stress}."
        )

        # Approximate illustrative cycle distribution, not measured sleep stages.
        deep_sleep = round(sleep_hours * 0.20, 2)
        rem_sleep = round(sleep_hours * 0.25, 2)
        light_sleep = round(max(0, sleep_hours - deep_sleep - rem_sleep), 2)

        return render_template(
            "result.html",
            stress=stress,
            health_score=max(0, min(100, int(100 - (
                (heart_rate > 90) * 10 +
                (respiratory_rate > 20) * 10 +
                (blood_oxygen < 95) * 15 +
                (sleep_hours < 7) * 15
            )))),
            deep_sleep=deep_sleep,
            rem_sleep=rem_sleep,
            light_sleep=light_sleep
        )

    return render_template("predict.html")


# ============================================================
# Prediction history
# ============================================================

@app.route("/history")
def history():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    try:
        records = conn.execute(
            """
            SELECT * FROM predictions
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (session["user_id"],)
        ).fetchall()
    finally:
        conn.close()

    # Provide both names so templates from earlier versions can be used.
    return render_template(
        "history.html",
        records=records,
        history=records
    )


# ============================================================
# Profile
# ============================================================

@app.route("/profile")
def profile():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        total_predictions = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE user_id = ?",
            (session["user_id"],)
        ).fetchone()[0]
    finally:
        conn.close()

    return render_template(
        "profile.html",
        user=user,
        total_predictions=total_predictions
    )


@app.route("/update_profile", methods=["POST"])
def update_profile():
    if not login_required():
        return redirect(url_for("login"))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    age_text = request.form.get("age", "").strip()
    gender = request.form.get("gender", "").strip()

    if not name or not email:
        flash("Name and email are required.", "error")
        return redirect(url_for("profile"))

    try:
        age = int(age_text) if age_text else None
    except ValueError:
        flash("Please enter a valid age.", "error")
        return redirect(url_for("profile"))

    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE users
            SET name = ?, email = ?, age = ?, gender = ?
            WHERE id = ?
            """,
            (name, email, age, gender or None, session["user_id"])
        )
        conn.commit()
        session["name"] = name
        session["email"] = email
        flash("Profile updated successfully.", "success")
    except sqlite3.IntegrityError:
        flash("That email is already used by another account.", "error")
    finally:
        conn.close()

    return redirect(url_for("profile"))


@app.route("/change_password", methods=["POST"])
def change_password():
    if not login_required():
        return redirect(url_for("login"))

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")

    if len(new_password) < 8:
        flash("New password must contain at least 8 characters.", "error")
        return redirect(url_for("profile"))

    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT password FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        if not user or not check_password_hash(
            user["password"], current_password
        ):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("profile"))

        conn.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (generate_password_hash(new_password), session["user_id"])
        )
        conn.commit()
        flash("Password changed successfully.", "success")
    finally:
        conn.close()

    return redirect(url_for("profile"))


# ============================================================
# Family and friends contacts
# ============================================================

@app.route("/family", methods=["GET"])
def family():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    try:
        members = conn.execute(
            """
            SELECT * FROM family_contacts
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (session["user_id"],)
        ).fetchall()
    finally:
        conn.close()

    return render_template("family.html", members=members, contacts=members)


@app.route("/add_contact", methods=["POST"])
def add_contact():
    if not login_required():
        return redirect(url_for("login"))

    name = request.form.get("contact_name", "").strip()
    relation = request.form.get("relationship", "").strip()
    email = request.form.get("contact_email", "").strip().lower()
    phone = request.form.get("contact_phone", "").strip()

    if not name:
        flash("Please enter the contact's name.", "error")
        return redirect(url_for("family"))

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO family_contacts
            (user_id, contact_name, relationship, contact_email, contact_phone)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session["user_id"], name, relation, email, phone)
        )
        conn.commit()
        flash("Family/friend contact added.", "success")
    finally:
        conn.close()

    return redirect(url_for("family"))


@app.route("/add_family", methods=["POST"])
def add_family():
    """Compatibility route for the earlier family.html form."""
    if not login_required():
        return redirect(url_for("login"))

    email = request.form.get("email", "").strip().lower()
    relation = request.form.get("relation", "Friend").strip()

    if not email:
        flash("Please enter a member email.", "error")
        return redirect(url_for("family"))

    conn = get_db_connection()
    try:
        # Only save the contact as a contact. This does not grant access to
        # that person's sleep data or automatically connect their account.
        conn.execute(
            """
            INSERT INTO family_contacts
            (user_id, contact_name, relationship, contact_email)
            VALUES (?, ?, ?, ?)
            """,
            (session["user_id"], email.split("@")[0], relation, email)
        )
        conn.commit()
        flash("Contact added. The person has not been granted data access.", "success")
    finally:
        conn.close()

    return redirect(url_for("family"))


@app.route("/contacts")
def contacts():
    return family()


@app.route("/delete_contact/<int:id>", methods=["POST", "GET"])
def delete_contact(id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    try:
        conn.execute(
            "DELETE FROM family_contacts WHERE id = ? AND user_id = ?",
            (id, session["user_id"])
        )
        conn.commit()
    finally:
        conn.close()

    flash("Contact removed.", "success")
    return redirect(url_for("family"))


# ============================================================
# Sleep analysis
# ============================================================

@app.route("/sleep_analysis")
def sleep_analysis():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT AVG(sleep_hours) AS avg_sleep,
                   COUNT(*) AS total_records
            FROM predictions
            WHERE user_id = ? AND sleep_hours IS NOT NULL
            """,
            (session["user_id"],)
        ).fetchone()

        recent = conn.execute(
            """
            SELECT DATE(created_at) AS sleep_date,
                   AVG(sleep_hours) AS avg_sleep
            FROM predictions
            WHERE user_id = ? AND sleep_hours IS NOT NULL
            GROUP BY DATE(created_at)
            ORDER BY sleep_date DESC
            LIMIT 7
            """,
            (session["user_id"],)
        ).fetchall()
    finally:
        conn.close()

    avg_sleep = round(row["avg_sleep"], 2) if row["avg_sleep"] is not None else None
    return render_template(
        "sleep_analysis.html",
        avg_sleep=avg_sleep,
        total_records=row["total_records"],
        recent=list(reversed(recent))
    )


# ============================================================
# Notifications
# ============================================================

@app.route("/notifications")
def notifications():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    try:
        alerts = conn.execute(
            """
            SELECT * FROM notifications
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 50
            """,
            (session["user_id"],)
        ).fetchall()
    finally:
        conn.close()

    return render_template("notifications.html", alerts=alerts)


# ============================================================
# Simple informational assistant
# ============================================================

@app.route("/chatbot")
def chatbot():
    if not login_required():
        return redirect(url_for("login"))
    return render_template("chatbot.html")


@app.route("/chatbot/ask", methods=["POST"])
def chatbot_ask():
    if not login_required():
        return jsonify({"answer": "Please log in first."}), 401

    question = request.get_json(silent=True) or {}
    message = str(question.get("question", "")).lower()

    if "stress" in message:
        answer = (
            "Consider a regular sleep schedule, gentle activity, and relaxation. "
            "This assistant cannot diagnose stress or replace professional care."
        )
    elif "sleep" in message or "cycle" in message:
        answer = (
            "Most adults need around 7–9 hours of sleep. Sleep-cycle durations "
            "vary, and this app cannot measure actual REM or deep sleep without "
            "appropriate sleep-tracking data."
        )
    elif "oxygen" in message:
        answer = (
            "Consumer readings can be inaccurate. If you have concerning symptoms "
            "or persistently low oxygen readings, seek medical advice."
        )
    else:
        answer = (
            "I can share general information about sleep, stress, and healthy "
            "routines. I cannot diagnose medical conditions."
        )

    return jsonify({"answer": answer})


# ============================================================
# Admin login and dashboard
# ============================================================

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        try:
            admin = conn.execute(
                "SELECT * FROM admin WHERE username = ?",
                (username,)
            ).fetchone()
        finally:
            conn.close()

        valid = False
        if admin:
            try:
                valid = check_password_hash(admin["password"], password)
            except (ValueError, TypeError):
                valid = admin["password"] == password

        if valid:
            session["admin_logged_in"] = True
            session["admin_name"] = username
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials.", "error")
        return redirect(url_for("admin_login"))

    return render_template("admin_login.html")


@app.route("/admin")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    try:
        total_users = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        total_predictions = conn.execute(
            "SELECT COUNT(*) FROM predictions"
        ).fetchone()[0]

        high_stress = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE stress_level = 'High'"
        ).fetchone()[0]

        users = conn.execute(
            "SELECT id, name, email, age, gender, created_at FROM users ORDER BY id DESC"
        ).fetchall()

        predictions = conn.execute(
            """
            SELECT predictions.*, users.name AS user_name
            FROM predictions
            LEFT JOIN users ON users.id = predictions.user_id
            ORDER BY predictions.id DESC
            LIMIT 20
            """
        ).fetchall()
    finally:
        conn.close()

    return render_template(
        "admin.html",
        total_users=total_users,
        total_predictions=total_predictions,
        active_users=total_users,
        high_stress=high_stress,
        users=users,
        predictions=predictions
    )


@app.route("/admin_logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_name", None)
    flash("Admin logged out.", "success")
    return redirect(url_for("admin_login"))


# ============================================================
# Error handlers
# ============================================================

@app.errorhandler(404)
def page_not_found(error):
    return "<h1>404 - Page Not Found</h1>", 404


@app.errorhandler(500)
def server_error(error):
    app.logger.exception("An internal server error occurred.")
    return "<h1>500 - Internal Server Error</h1>", 500


# ============================================================
# Run application
# ============================================================

if __name__ == "__main__":
    # Debug is useful for local development only. Disable it for deployment.
    app.run(host="127.0.0.1", port=5000, debug=True)
