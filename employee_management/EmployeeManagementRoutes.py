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

employee_bp = Blueprint(
    "employee", 
    __name__, 
    template_folder="templates"
)

@employee_bp.route("/employees")
@login_required
def employees():
    """ Displays a table with employee information """
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

    # Shows wage of employees based on the current user's access level
    employees = []
    for row in cursor.fetchall():
        employee_id = row["employee_id"]
        account_level = row["system_role_id"]
        hourly_rate = None

        # Admins see all
        if current_user.system_role_id == 3:
            hourly_rate = row["hourly_rate"]
        # Managers see their own wage and Associates wages
        elif current_user.system_role_id == 2:
            if account_level == 1 or employee_id == current_user.employee_id:
                hourly_rate = row["hourly_rate"]
        # Associates only see their own wage
        elif employee_id == current_user.employee_id:
            hourly_rate = row["hourly_rate"]

        # Add data to employees to be put into the table
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

#TODO: 400 call with errors when adding employee fails, and display errors on the page
@employee_bp.route("/add_employee", methods=["POST"])
@login_required
def add_employee():
    first_name = request.form["first_name"].strip()
    last_name = request.form["last_name"].strip()
    role_name = request.form["role_name"].strip()
    level = int(request.form["level"])
    hourly_rate = request.form["wage"].strip()
    username = request.form.get("username", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

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

    cursor.execute(
        """
        INSERT INTO Employees
        (role_id, first_name, last_name, hourly_rate)
        VALUES (?, ?, ?, ?)
        """,
        (role_id, first_name, last_name, hourly_rate),
    )
    employee_id = cursor.lastrowid

    if username:
        user = cursor.execute(
            "SELECT userid FROM Users WHERE username = ?",
            (username,),
        ).fetchone()
        if user:
            cursor.execute(
                "UPDATE Users SET employee_id = ? WHERE userid = ?",
                (employee_id, user["userid"]),
            )
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

@employee_bp.route("/api/employees")
def api_employees():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT first_name, last_name, role_id, hourly_rate
        FROM Employees
    """)
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