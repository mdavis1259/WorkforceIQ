
from pathlib import Path
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).parent / "workforce.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Proof of Concept: User Authentication
cursor.execute("""
CREATE TABLE IF NOT EXISTS Users(
    userid INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
""")

# Create a demo account only if it does not already exist.
cursor.execute(
    "SELECT 1 FROM Users WHERE username = ?",
    ("admin",)
)

if cursor.fetchone() is None:
    cursor.execute("""
        INSERT INTO Users(username, password)
        VALUES (?, ?)
    """, ("admin", generate_password_hash("password")))

# Proof of Concept: Employee Management
cursor.execute("""
CREATE TABLE IF NOT EXISTS employees(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    wage REAL NOT NULL
)
""")

conn.commit()
conn.close()

print("WorkforceIQ proof-of-concept database created.")
