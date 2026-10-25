from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).parent / "workforce.db"

conn = sqlite3.connect(DB_PATH)

cursor = conn.cursor()

# ---------------------------------------
# Proof of Concept
# User Authentication
# ---------------------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS Users(
    userid INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password TEXT NOT NULL
)
""")

cursor.execute("""
INSERT INTO Users(username, password)
VALUES('admin', 'password')
""")

# ---------------------------------------
# Proof of Concept
# Employee Management
# ---------------------------------------

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
