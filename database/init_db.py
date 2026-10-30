
from pathlib import Path
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).parent / "workforce.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Drop existing tables
# TODO: remove later, only for development purposes
cursor.execute("DROP TABLE IF EXISTS Employees")
cursor.execute("DROP TABLE IF EXISTS Users")

# Proof of Concept: User Authentication
# Levels 0 = Unregistered, 1 = Employee, 2 = Manager, 3 = Admin
cursor.execute("""
CREATE TABLE IF NOT EXISTS Users(
    userid INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT chk_level CHECK(
        level IN (0, 1, 2, 3)) 
)
""")

# Create a demo account only if it does not already exist.
cursor.execute(
    "SELECT 1 FROM Users WHERE username = ?",
    ("admin",)
)

if cursor.fetchone() is None:
    cursor.execute("""
        INSERT INTO Users(username, password, level)
        VALUES
        (?, ?, ?),
        (?, ?, ?),
        (?, ?, ?)
    """, (
        "admin", generate_password_hash("password"), 3,
        "manager", generate_password_hash("password"), 0,
        "employee", generate_password_hash("password"), 0
    ))

# Proof of Concept: Employee Management
cursor.execute("""
CREATE TABLE IF NOT EXISTS Employees(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    wage REAL NOT NULL,
    userid INTEGER NOT NULL,
    CONSTRAINT fk_userid FOREIGN KEY (userid) REFERENCES Users(userid)
)

""")

conn.commit()
conn.close()

print("WorkforceIQ proof-of-concept database created/updated.")
