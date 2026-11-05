"""Employee profile logic for WorkforceIQ (US-3).

Every function takes an open sqlite3 connection (conn). The connection
should use row_factory = sqlite3.Row, which get_db_connection() in
app.py already sets.
"""
from decimal import Decimal, InvalidOperation

MAX_NAME_LENGTH = 50
MAX_HOURLY_WAGE = Decimal("1000")


# ----------------------------------------------------------
# Validation
# ----------------------------------------------------------
def validate_employee(conn, first_name, last_name, role_id, hourly_wage):
    """Check employee form data.

    Returns (clean, errors). clean is a dict of cleaned values and
    errors is a list of messages. If errors is empty, clean is safe
    to save.
    """
    errors = []

    first_name = (first_name or "").strip()
    last_name = (last_name or "").strip()

    if not first_name:
        errors.append("First name is required.")
    elif len(first_name) > MAX_NAME_LENGTH:
        errors.append(f"First name must be {MAX_NAME_LENGTH} characters or fewer.")

    if not last_name:
        errors.append("Last name is required.")
    elif len(last_name) > MAX_NAME_LENGTH:
        errors.append(f"Last name must be {MAX_NAME_LENGTH} characters or fewer.")

    # Role must be a number that exists in the Roles table
    try:
        role_id = int(role_id)
    except (TypeError, ValueError):
        role_id = None
        errors.append("A job role must be selected.")
    else:
        found = conn.execute(
            "SELECT 1 FROM Roles WHERE role_id = ?", (role_id,)
        ).fetchone()
        if found is None:
            errors.append("The selected job role does not exist.")

    # Wage must be a number between 0 and MAX_HOURLY_WAGE
    try:
        wage = Decimal(str(hourly_wage).strip())
        if wage < 0 or wage > MAX_HOURLY_WAGE:
            errors.append(f"Hourly wage must be between 0 and {MAX_HOURLY_WAGE}.")
    except (InvalidOperation, ValueError):
        wage = None
        errors.append("Hourly wage must be a number.")

    clean = {
        "first_name": first_name,
        "last_name": last_name,
        "role_id": role_id,
        "hourly_wage": float(wage) if wage is not None else None,
    }
    return clean, errors


# ----------------------------------------------------------
# Lookups for dropdowns / checkboxes
# ----------------------------------------------------------
def list_roles(conn):
    return conn.execute(
        "SELECT role_id, role_name FROM Roles ORDER BY role_name"
    ).fetchall()


def list_qualifications(conn):
    return conn.execute(
        "SELECT qualification_id, qualification_name "
        "FROM Qualifications ORDER BY qualification_name"
    ).fetchall()


def create_qualification(conn, name):
    """Add a new qualification. Returns its id, or None if the name
    is blank or already exists."""
    name = (name or "").strip()
    if not name:
        return None
    existing = conn.execute(
        "SELECT qualification_id FROM Qualifications "
        "WHERE LOWER(qualification_name) = LOWER(?)",
        (name,),
    ).fetchone()
    if existing:
        return None
    cursor = conn.execute(
        "INSERT INTO Qualifications (qualification_name) VALUES (?)", (name,)
    )
    conn.commit()
    return cursor.lastrowid


# ----------------------------------------------------------
# Read
# ----------------------------------------------------------
def list_employees(conn, search=None):
    """Return all employees with their role name and a comma-separated
    list of qualifications. If search is given, match it against first
    name, last name, role name, or any qualification name."""
    sql = """
        SELECT
            e.employee_id,
            e.first_name,
            e.last_name,
            e.hourly_wage,
            r.role_id,
            r.role_name,
            GROUP_CONCAT(q.qualification_name, ', ') AS qualifications
        FROM Employees e
        JOIN Roles r ON r.role_id = e.role_id
        LEFT JOIN EmployeeQualifications eq ON eq.employee_id = e.employee_id
        LEFT JOIN Qualifications q ON q.qualification_id = eq.qualification_id
    """
    params = []
    search = (search or "").strip()
    if search:
        like = f"%{search}%"
        sql += """
        WHERE e.first_name LIKE ?
           OR e.last_name LIKE ?
           OR (e.first_name || ' ' || e.last_name) LIKE ?
           OR r.role_name LIKE ?
           OR EXISTS (
                SELECT 1
                FROM EmployeeQualifications eq2
                JOIN Qualifications q2
                  ON q2.qualification_id = eq2.qualification_id
                WHERE eq2.employee_id = e.employee_id
                  AND q2.qualification_name LIKE ?
           )
        """
        params = [like, like, like, like, like]
    sql += " GROUP BY e.employee_id ORDER BY e.last_name, e.first_name"
    return conn.execute(sql, params).fetchall()


def get_employee(conn, employee_id):
    """Return one employee (or None) plus a list of their qualification ids."""
    employee = conn.execute(
        """
        SELECT e.employee_id, e.first_name, e.last_name, e.hourly_wage,
               r.role_id, r.role_name
        FROM Employees e
        JOIN Roles r ON r.role_id = e.role_id
        WHERE e.employee_id = ?
        """,
        (employee_id,),
    ).fetchone()
    if employee is None:
        return None, []
    rows = conn.execute(
        "SELECT qualification_id FROM EmployeeQualifications WHERE employee_id = ?",
        (employee_id,),
    ).fetchall()
    return employee, [row["qualification_id"] for row in rows]


# ----------------------------------------------------------
# Create / Update / Delete
# ----------------------------------------------------------
def set_qualifications(conn, employee_id, qualification_ids):
    """Replace the employee's qualifications with the given list of ids."""
    conn.execute(
        "DELETE FROM EmployeeQualifications WHERE employee_id = ?", (employee_id,)
    )
    for qualification_id in set(qualification_ids or []):
        conn.execute(
            "INSERT INTO EmployeeQualifications (employee_id, qualification_id) "
            "VALUES (?, ?)",
            (employee_id, int(qualification_id)),
        )
    conn.commit()


def create_employee(conn, clean, qualification_ids=None):
    """Insert an employee using cleaned data from validate_employee().
    Returns the new employee_id."""
    cursor = conn.execute(
        "INSERT INTO Employees (role_id, first_name, last_name, hourly_wage) "
        "VALUES (?, ?, ?, ?)",
        (clean["role_id"], clean["first_name"], clean["last_name"],
         clean["hourly_wage"]),
    )
    employee_id = cursor.lastrowid
    conn.commit()
    set_qualifications(conn, employee_id, qualification_ids)
    return employee_id


def update_employee(conn, employee_id, clean, qualification_ids=None):
    """Update an employee. Returns True if the employee existed."""
    cursor = conn.execute(
        "UPDATE Employees SET role_id = ?, first_name = ?, last_name = ?, "
        "hourly_wage = ? WHERE employee_id = ?",
        (clean["role_id"], clean["first_name"], clean["last_name"],
         clean["hourly_wage"], employee_id),
    )
    conn.commit()
    if cursor.rowcount == 0:
        return False
    set_qualifications(conn, employee_id, qualification_ids)
    return True


def delete_employee(conn, employee_id):
    """Delete an employee and their qualification links.

    Raises ValueError if a login account is linked to the employee,
    because Users.employee_id is NOT NULL and the account would break.
    Returns True if an employee was deleted.
    """
    linked_user = conn.execute(
        "SELECT 1 FROM Users WHERE employee_id = ?", (employee_id,)
    ).fetchone()
    if linked_user:
        raise ValueError("This employee has a login account and cannot be deleted.")
    conn.execute(
        "DELETE FROM EmployeeQualifications WHERE employee_id = ?", (employee_id,)
    )
    cursor = conn.execute(
        "DELETE FROM Employees WHERE employee_id = ?", (employee_id,)
    )
    conn.commit()
    return cursor.rowcount > 0