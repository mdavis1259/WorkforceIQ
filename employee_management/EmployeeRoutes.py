"""
Employee Management Routes

Per the WorkforceIQ SDS, the Employee Management Module
is responsible for:

    - Employee records
    - Job roles
    - Qualifications
    - Wage information

Routes are part of the Presentation Layer and are
responsible for:

    - Receiving HTTP requests
    - Validating request data
    - Calling service methods
    - Returning responses

Per SDS Section 4.2:

    Routes
        ↓
    EmployeeService
        ↓
    EmployeeRepository
        ↓
        SQLite

Current Status:
    This module is being refactored toward the SDS
    architecture. Some routes still contain SQL and
    business rules that should eventually be moved
    into EmployeeService and EmployeeRepository.
"""

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
)

from flask_login import (
    login_required,
    current_user,
)

from database.connection import get_db_connection

from werkzeug.security import generate_password_hash


# =====================================================
# EMPLOYEE MANAGEMENT BLUEPRINT
# =====================================================

employee_bp = Blueprint(
    "employee",
    __name__,
    template_folder="templates"
)


# =====================================================
# EMPLOYEE DIRECTORY
# =====================================================

@employee_bp.route("/employees")
@login_required
def employees():
    """
    Display employee records.

    SDS Responsibility:
        Employee Management Module

    Architectural Note:
        This route currently retrieves employee
        information directly from the database.

    Future Architecture:

        EmployeeRoutes
            ↓
        EmployeeService.list_employees()
            ↓
        EmployeeRepository
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            Employees.employee_id,
            Employees.first_name,
            Employees.last_name,
            Roles.role_name,
            CASE
                Roles.system_role_id
                WHEN 0 THEN 'Unregistered'
                WHEN 1 THEN 'Associate'
                WHEN 2 THEN 'Manager'
                WHEN 3 THEN 'Administrator'
            END AS account_level,
            Roles.system_role_id,
            Employees.hourly_rate
        FROM Employees
        LEFT JOIN Roles ON Roles.role_id = Employees.role_id
        """
    )

    # SDS Requirement:
    # Wage information visibility depends on user role.
    # Employees should only see information appropriate
    # to their authorization level.
    employees = []

    for row in cursor.fetchall():

        employee_id = row["employee_id"]
        account_level = row["system_role_id"]
        hourly_rate = None

        # Administrators can view all wage information.
        if current_user.system_role_id == 3:
            hourly_rate = row["hourly_rate"]

        # Managers can view their own wage and
        # wages for Associate-level employees.
        elif current_user.system_role_id == 2:
            if (
                account_level == 1
                or employee_id == current_user.employee_id
            ):
                hourly_rate = row["hourly_rate"]

        # Associates may only view their own wage.
        elif employee_id == current_user.employee_id:
            hourly_rate = row["hourly_rate"]

        # Build employee data for presentation.
        employees.append((
            row["first_name"],
            row["last_name"],
            row["role_name"],
            row["account_level"],
            hourly_rate,
        ))

    conn.close()

    return render_template(
        "employees.html",
        employees=employees,
        restricted=(current_user.system_role_id == 1)
    )


# =====================================================
# CREATE EMPLOYEE
# =====================================================

# TODO:
# Return SDS-compliant validation errors (400)
# and display them on the Employee Management page.

@employee_bp.route("/add_employee", methods=["POST"])
@login_required
def add_employee():
    """
    Create a new employee record.

    SDS Responsibility:
        Employee Management Module

    Architectural Note:

        This route currently performs work that
        crosses multiple modules:

            Employee Management
                - Employee creation
                - Role assignment

            User Management
                - User account linkage

            Authentication
                - Initial credential creation

    Future Architecture:

        EmployeeRoutes
            ↓
        EmployeeService.create_employee()
            ↓
        EmployeeRepository

    User-account operations should eventually be
    delegated to User Management through service
    interfaces rather than direct database access.
    """

    first_name = request.form["first_name"].strip()
    last_name = request.form["last_name"].strip()
    role_name = request.form["role_name"].strip()
    level = int(request.form["level"])
    hourly_rate = request.form["wage"].strip()
    username = request.form.get("username", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Retrieve an existing role or create a new role
    # if one does not already exist.
    role_row = cursor.execute(
        "SELECT role_id FROM Roles WHERE role_name = ?",
        (role_name,),
    ).fetchone()

    if role_row is None:
        cursor.execute(
            "INSERT INTO Roles (role_name, system_role_id) VALUES (?, ?)",
            (role_name, level),
        )
        role_id = cursor.lastrowid
    else:
        role_id = role_row["role_id"]

    # Create employee record.
    cursor.execute(
        """
        INSERT INTO Employees
        (role_id, first_name, last_name, hourly_rate)
        VALUES (?, ?, ?, ?)
        """,
        (role_id, first_name, last_name, hourly_rate),
    )

    employee_id = cursor.lastrowid

    # If a username was supplied, associate the employee
    # with an existing account or create a new account.
    if username:

        user = cursor.execute(
            "SELECT userid FROM Users WHERE username = ?",
            (username,),
        ).fetchone()

        # Link existing account.
        if user:
            cursor.execute(
                "UPDATE Users SET employee_id = ? WHERE userid = ?",
                (employee_id, user["userid"]),
            )

        # Create new account.
        else:
            cursor.execute(
                """
                INSERT INTO Users
                (username, password, system_role_id, employee_id)
                VALUES (?, ?, ?, ?)
                """,
                (
                    username,
                    generate_password_hash("password"),
                    level,
                    employee_id,
                ),
            )

    conn.commit()
    conn.close()

    return redirect(url_for("employee.employees"))


# =====================================================
# EMPLOYEE API
# =====================================================

@employee_bp.route("/api/employees")
def api_employees():
    """
    Return employee information as JSON.

    SDS Endpoint:
        GET /api/employees

    Used by:
        - Employee Management views
        - AI Assistant context generation
        - Future integration points

    Architectural Note:
        This route currently executes SQL directly.
        Future versions should delegate employee
        retrieval to EmployeeService.
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT first_name, last_name, role_id, hourly_rate
        FROM Employees
        """
    )

    results = []

    for row in cursor.fetchall():

        role_name = cursor.execute(
            "SELECT role_name FROM Roles WHERE role_id = ?",
            (row["role_id"],),
        ).fetchone()

        results.append({
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "role": role_name["role_name"] if role_name else None,
            "hourly_rate": row["hourly_rate"],
        })

    conn.close()

    return jsonify(results)