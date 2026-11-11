
from pathlib import Path
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).parent / "workforce.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Drop existing tables
# TODO: remove later, only for development purposes
cursor.execute("DROP TABLE IF EXISTS EmployeeAvailability")
cursor.execute("DROP TABLE IF EXISTS Shifts")
cursor.execute("DROP TABLE IF EXISTS Workdays")
cursor.execute("DROP TABLE IF EXISTS SystemRoles")
cursor.execute("DROP TABLE IF EXISTS Roles")
cursor.execute("DROP TABLE IF EXISTS Employees")
cursor.execute("DROP TABLE IF EXISTS Users")

cursor.execute("""
CREATE TABLE IF NOT EXISTS SystemRoles(
    system_role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT NOT NULL UNIQUE,
    description TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Roles(
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT NOT NULL UNIQUE,
    system_role_id INTEGER NOT NULL,
    CONSTRAINT fk_system_role_id
        FOREIGN KEY (system_role_id) 
        REFERENCES SystemRoles(system_role_id)
)
""")

# Proof of Concept: Employee Management
cursor.execute("""
CREATE TABLE IF NOT EXISTS Employees(
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    hourly_wage REAL NOT NULL,
    CONSTRAINT fk_role_id
        FOREIGN KEY (role_id)
        REFERENCES Roles(role_id)
)
""")

# Proof of Concept: User Authentication
# Levels 0 = Unregistered, 1 = Employee, 2 = Manager, 3 = Admin
cursor.execute("""
CREATE TABLE IF NOT EXISTS Users(
    userid INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    system_role_id INTEGER NOT NULL DEFAULT 0,
    employee_id INTEGER NOT NULL,
    CONSTRAINT fk_system_role_id
        FOREIGN KEY (system_role_id) 
        REFERENCES SystemRoles(system_role_id),
    CONSTRAINT fk_employee_id
        FOREIGN KEY (employee_id) 
        REFERENCES Employees(employee_id)
)
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS Shifts(
        shift_id INTEGER PRIMARY KEY AUTOINCREMENT,
        shift_name TEXT NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME NOT NULL,
        active INTEGER NOT NULL DEFAULT 1
        CONSTRAINT boolean_active
                    CHECK (active IN (0, 1))
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS EmployeeAvailability(
        employee_availability_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        shift_id INTEGER NOT NULL,
        availability INTEGER NOT NULL DEFAULT 1,
        
        CONSTRAINT fk_employee_id
            FOREIGN KEY (employee_id)
            REFERENCES Employees(employee_id),
        CONSTRAINT fk_shift_id
            FOREIGN KEY (shift_id)
            REFERENCES Shifts(shift_id),
        CONSTRAINT boolean_availability
            CHECK (availability IN (0, 1))
    )
""")

# Create system roles, keep for final version
cursor.executemany(
    """
    INSERT INTO SystemRoles (system_role_id, role_name, description)
    VALUES
        (?, ?, ?)
    """,
    [
        (0, 'Unregistered', 'Unregistered user with no access'),
        (1, 'Associate', 'Regular employee with limited access'),
        (2, 'Manager', 'Manager with view of Employees and ability to make schedules'),
        (3, 'Administrator', 'Administrator with full access')
    ]
)

# Temporary roles for proof-of-concept, can be removed later
cursor.executemany(
    """
    INSERT INTO Roles (role_name, system_role_id)
    VALUES
        (?, ?)
    """,
    [
        ('Example Associate', 1),
        ('Example Manager', 2),
        ('Example Administrator', 3)
    ]
)

cursor.executemany(
    """
    INSERT INTO Employees (role_id, first_name, last_name, hourly_wage)
    VALUES (?, ?, ?, ?)
    """,
    [
        (1, 'April', 'Associate', 15.00),
        (2, 'Bob', 'Manager', 20.00),
        (3, 'Charlie', 'Administrator', 25.00)
    ],
)

cursor.executemany(
    """
    INSERT INTO Users (username, password, system_role_id, employee_id)
    VALUES (?, ?, ?, ?)
    """,
    [
        ('april', generate_password_hash('password'), 1, 1),
        ('bob', generate_password_hash('password'), 2, 2),
        ('admin', generate_password_hash('password'), 3, 3),
    ],
)

cursor.executemany(
    """
    INSERT INTO Shifts (shift_name, start_time, end_time, active)
    VALUES (?, ?, ?, ?)
    """,
    [
        ('Morning Shift', '2026-11-10T08:00:00', '2026-11-10T12:00:00', 1),
        ('Afternoon Shift', '2026-11-10T12:00:00', '2026-11-10T16:00:00', 1),
        ('Evening Shift', '2026-11-10T16:00:00', '2026-11-10T20:00:00', 1),
    ],
)

cursor.executemany(
    """
    INSERT INTO EmployeeAvailability (employee_id, shift_id, availability)
    VALUES (?, ?, ?)
    """,
    [
        (1, 1, 1),
        (1, 2, 0),
        (1, 3, 1),
        (2, 1, 1),
        (2, 2, 1),
        (2, 3, 0),
        (3, 1, 0),
        (3, 2, 1),
        (3, 3, 1),
    ],
)
conn.commit()
conn.close()

print("WorkforceIQ proof-of-concept database created/updated.")
