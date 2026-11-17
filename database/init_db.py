from pathlib import Path
import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).parent / "workforce.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Drop existing tables
# TODO: remove later, only for development purposes
cursor.execute("DROP TABLE IF EXISTS ShiftAssignments")
cursor.execute("DROP TABLE IF EXISTS Schedules")
cursor.execute("DROP TABLE IF EXISTS StaffingRequirements")
cursor.execute("DROP TABLE IF EXISTS Forecasts")
cursor.execute("DROP TABLE IF EXISTS DemandHistory")
cursor.execute("DROP TABLE IF EXISTS TimeOffRequests")
cursor.execute("DROP TABLE IF EXISTS EmployeeAvailability")
cursor.execute("DROP TABLE IF EXISTS Shifts")

cursor.execute("DROP TABLE IF EXISTS EmployeeQualifications")
cursor.execute("DROP TABLE IF EXISTS Qualifications")
cursor.execute("DROP TABLE IF EXISTS Users")
cursor.execute("DROP TABLE IF EXISTS Employees")
cursor.execute("DROP TABLE IF EXISTS Roles")
cursor.execute("DROP TABLE IF EXISTS SystemRoles")

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
hourly_rate REAL NOT NULL,
max_hours_per_week INTEGER NOT NULL DEFAULT 40,
preferred_hours_per_week INTEGER NOT NULL DEFAULT 32,
active INTEGER NOT NULL DEFAULT 1,
CONSTRAINT fk_role_id
FOREIGN KEY (role_id)
REFERENCES Roles(role_id)
)
""")

# US-3: Qualifications (certifications/skills an employee can hold)
cursor.execute("""
CREATE TABLE IF NOT EXISTS Qualifications(
qualification_id INTEGER PRIMARY KEY AUTOINCREMENT,
qualification_name TEXT NOT NULL UNIQUE
)
""")

# US-3: Many-to-many link between Employees and Qualifications
cursor.execute("""
CREATE TABLE IF NOT EXISTS EmployeeQualifications(
employee_id INTEGER NOT NULL,
qualification_id INTEGER NOT NULL,
PRIMARY KEY (employee_id, qualification_id),
CONSTRAINT fk_eq_employee
FOREIGN KEY (employee_id) REFERENCES Employees(employee_id),
CONSTRAINT fk_eq_qualification
FOREIGN KEY (qualification_id) REFERENCES Qualifications(qualification_id)
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
active INTEGER NOT NULL DEFAULT 1,
force_password_reset INTEGER NOT NULL DEFAULT 1,

CONSTRAINT fk_system_role_id
FOREIGN KEY (system_role_id)
REFERENCES SystemRoles(system_role_id),

CONSTRAINT fk_employee_id
FOREIGN KEY (employee_id)
REFERENCES Employees(employee_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Workdays(
    workday_id INTEGER PRIMARY KEY,
    day_name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Shifts(
    shift_id INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_name TEXT NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS DemandHistory(
    demand_id INTEGER PRIMARY KEY AUTOINCREMENT,
    demand_date TEXT NOT NULL,
    sales_amount REAL NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Forecasts(
    forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_date TEXT NOT NULL UNIQUE,
    projected_sales REAL NOT NULL,
    projected_sales_low REAL NOT NULL,
    projected_sales_high REAL NOT NULL,
    required_labor_hours REAL,
    labor_budget REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'Draft'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS StaffingRequirements(
    requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workday_id INTEGER NOT NULL,
    shift_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    required_count INTEGER NOT NULL,          

    FOREIGN KEY (workday_id)
        REFERENCES Workdays(workday_id)

    FOREIGN KEY (shift_id)
        REFERENCES Shifts(shift_id),
        
    FOREIGN KEY (role_id)
        REFERENCES Roles(role_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Schedules(
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Draft'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ShiftAssignments(
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,

    schedule_id INTEGER NOT NULL,
    employee_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    shift_id INTEGER NOT NULL,

    schedule_date TEXT NOT NULL,
    hours REAL NOT NULL,

    FOREIGN KEY (schedule_id)
        REFERENCES Schedules(schedule_id),

    FOREIGN KEY (employee_id)
        REFERENCES Employees(employee_id),

    FOREIGN KEY (role_id)
        REFERENCES Roles(role_id),

    FOREIGN KEY (shift_id)
        REFERENCES Shifts(shift_id)

    UNIQUE(
        schedule_id,
        employee_id,
        shift_id,
        schedule_date
    )
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

# Create Workdays, keep for final version
cursor.executemany(
    """
    INSERT INTO Workdays (workday_id, day_name, active)
    VALUES (?, ?, ?)
    """,
    [
        (0, 'Monday', 1),
        (1, 'Tuesday', 1),
        (2, 'Wednesday', 1),
        (3, 'Thursday', 1),
        (4, 'Friday', 1),
        (5, 'Saturday', 1),
        (6, 'Sunday', 1)
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
    INSERT INTO Employees (role_id, first_name, last_name, hourly_rate)
    VALUES (?, ?, ?, ?)
    """,
    [
        (1, 'April', 'Associate', 15.00),
        (2, 'Bob', 'Manager', 20.00),
        (3, 'Charlie', 'Administrator', 25.00)
    ],
)

# US-3: seed qualifications and link them to the example employees
cursor.executemany(
    "INSERT INTO Qualifications (qualification_name) VALUES (?)",
    [
        ('Food Handler Certified',),
        ('Cash Handling',),
        ('Opening Shift',),
        ('Closing Shift',),
        ('First Aid / CPR',)
    ]
)

cursor.executemany(
    "INSERT INTO EmployeeQualifications (employee_id, qualification_id) VALUES (?, ?)",
    [
        (1, 1), (1, 2),
        (2, 1), (2, 2), (2, 3), (2, 4),
        (3, 5)
    ]
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
    INSERT INTO Shifts (shift_name, start_time, end_time)
    VALUES (?, ?, ?)
    """,
    [
        ('Morning Shift', '08:00', '12:00'),
        ('Afternoon Shift', '12:00', '16:00'),
        ('Evening Shift', '16:00', '20:00'),
    ],
)

cursor.executemany(
    """
    INSERT INTO DemandHistory
    (demand_date, sales_amount)
    VALUES (?, ?)
    """,
    [
        ("2026-10-01", 4500),
        ("2026-10-02", 4700),
        ("2026-10-03", 6200),
        ("2026-10-04", 5900),
        ("2026-10-05", 4600),
        ("2026-10-06", 4550),
        ("2026-10-07", 4800),

        ("2026-10-08", 4650),
        ("2026-10-09", 4850),
        ("2026-10-10", 6400),
        ("2026-10-11", 6100),
        ("2026-10-12", 4700),
        ("2026-10-13", 4600),
        ("2026-10-14", 4900),

        ("2026-10-15", 4750),
        ("2026-10-16", 5000),
        ("2026-10-17", 6600),
        ("2026-10-18", 6300),
        ("2026-10-19", 4800),
        ("2026-10-20", 4700),
        ("2026-10-21", 4950),

        ("2026-10-22", 4900),
        ("2026-10-23", 5150),
        ("2026-10-24", 6750),
        ("2026-10-25", 6500),
        ("2026-10-26", 4900),
        ("2026-10-27", 4800),
        ("2026-10-28", 5100),

        ("2026-10-29", 5050),
        ("2026-10-30", 5300),
        ("2026-10-31", 7000),
        ("2026-11-01", 6700),
        ("2026-11-02", 5000),
        ("2026-11-03", 4950),
        ("2026-11-04", 5200),
    ],
)

cursor.executemany(
    """
    INSERT INTO Workdays(
        workday_id,
        day_name,
        active
    )
    VALUES (?, ?, ?)
    """,
    [
        (1, "Monday", 1),
        (2, "Tuesday", 1),
        (3, "Wednesday", 1),
        (4, "Thursday", 1),
        (5, "Friday", 1),
        (6, "Saturday", 1),
        (7, "Sunday", 1)
    ]
)

staffing_requirements = [

    # Monday
    (1, 1, 1, 2),  # 2 associates morning
    (1, 1, 2, 1),  # 1 lead morning
    (1, 2, 1, 3),  # 3 associates evening
    (1, 2, 2, 1),  # 1 lead evening

    # Tuesday
    (2, 1, 1, 2),
    (2, 1, 2, 1),
    (2, 2, 1, 3),
    (2, 2, 2, 1),

    # Wednesday
    (3, 1, 1, 2),
    (3, 1, 2, 1),
    (3, 2, 1, 3),
    (3, 2, 2, 1),

    # Thursday
    (4, 1, 1, 2),
    (4, 1, 2, 1),
    (4, 2, 1, 3),
    (4, 2, 2, 1),

    # Friday
    (5, 1, 1, 3),
    (5, 1, 2, 1),
    (5, 2, 1, 4),
    (5, 2, 2, 1),

    # Saturday
    (6, 1, 1, 3),
    (6, 1, 2, 1),
    (6, 2, 1, 4),
    (6, 2, 2, 1),

    # Sunday
    (7, 1, 1, 2),
    (7, 1, 2, 1),
    (7, 2, 1, 3),
    (7, 2, 2, 1),
]

for (
    workday_id,
    shift_id,
    role_id,
    required_count
) in staffing_requirements:

    cursor.execute("""
        INSERT INTO StaffingRequirements (
            workday_id,
            shift_id,
            role_id,
            required_count
        )
        VALUES (?, ?, ?, ?)
    """, (
        workday_id,
        shift_id,
        role_id,
        required_count
    ))

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