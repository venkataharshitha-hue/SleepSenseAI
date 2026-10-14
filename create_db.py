import sqlite3

conn = sqlite3.connect("database.db")

cursor = conn.cursor()

# =========================
# USERS TABLE
# =========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,

    email TEXT UNIQUE NOT NULL,

    password TEXT NOT NULL,

    age INTEGER,

    gender TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

)
""")

# =========================
# PREDICTIONS TABLE
# =========================

cursor.execute("""
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

    prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id)
    REFERENCES users(id)

)
""")

# =========================
# FAMILY CONTACTS TABLE
# =========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS family_contacts (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER,

    contact_name TEXT,

    relationship TEXT,

    contact_email TEXT,

    contact_phone TEXT,

    FOREIGN KEY(user_id)
    REFERENCES users(id)

)
""")

# =========================
# ADMIN TABLE
# =========================

cursor.execute("""
CREATE TABLE IF NOT EXISTS admin (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    username TEXT UNIQUE,

    password TEXT

)
""")

# Default Admin

cursor.execute("""
INSERT OR IGNORE INTO admin
(id, username, password)
VALUES
(1,'admin','admin123')
""")

conn.commit()

conn.close()

print("Database Created Successfully")