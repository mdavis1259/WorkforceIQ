import sqlite3
from tkinter import LEFT
import requests
import numpy as np
from decimal import Decimal, InvalidOperation
from auth import authenticate_user
from sklearn.linear_model import LinearRegression
from werkzeug.security import generate_password_hash
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.secret_key = (
    app.config.get("SECRET_KEY")
    or "development-key-change-in-production"
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class User(UserMixin):
    def __init__(self, userid, username, system_role_id, employee_id=None):
        self.id = userid
        self.userid = userid
        self.username = username
        self.system_role_id = system_role_id
        self.employee_id = employee_id

# ======================================================
# HELPER FUNCTIONS
# ======================================================

def get_db_connection():
    #Uses regular database by default, but can be overridden for testing
    database = app.config.get("DATABASE", "database/workforce.db") 
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row #Lets us access columns by name instead of index
    return connection

def get_employee_context():
    employees = requests.get("http://127.0.0.1:5000/api/employees").json()
    context = "Current Employees:\n\n"
    for employee in employees:
        context += (
            f"Name: {employee["first_name"].strip() + ' ' + employee["last_name"].strip()}, "
            f"Role: {employee['role']}, "
            f"Wage: ${employee["hourly_wage"]}/hr\n"
        )
    print("Employee Context:\n" + context) #TODO: Remove this debug print statement in production
    return context
        
def generate_forecast():
    # Sample historical demand data
    days = np.array([1, 2, 3, 4, 5]).reshape(-1, 1)

    demand = np.array([100, 120, 140, 160, 180])

    model = LinearRegression()
    model.fit(days, demand)
    prediction = model.predict([[6]])

    return round(prediction[0])

def ask_ollama(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False
        }
    )

    data = response.json()

    if "response" in data:
        return data["response"]

    if "error" in data:
        return f"Error: {data['error']}"

    return "Unknown response received."

# =====================================================
# DATABASE UTILITIES
# =====================================================

# =====================================================
# LOGIN MANAGER
# =====================================================
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM Users WHERE userid = ?",
        (user_id,)
    )
    user = cursor.fetchone()
    conn.close()
    if user is None:
        return None
    return User(
        userid=user["userid"],
        username=user["username"],
        system_role_id=user["system_role_id"],
        employee_id=user["employee_id"],
    )

# =====================================================
# AUTHENTICATION ROUTES
# =====================================================
@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()

        try:
            user = authenticate_user(username, password, conn)
        finally:
            conn.close()

        if user:
            authenticated_user = User(
                userid=user["userid"],
                username=user["username"],
                system_role_id=user["system_role_id"],
                employee_id=user["employee_id"],
            )
            login_user(authenticated_user)

            # User is unassigned, sets own level TODO: remove once login redirection is implemnnted
            if authenticated_user.system_role_id == 0:
                return redirect(url_for("level_select"))

            # Else, go to dashboard
            return redirect(url_for("dashboard"))

        error = "Invalid username or password."
        
    return render_template("login.html", error=error)

# Registration for new users.
@app.route("/register", methods=["POST"])
def register():
    # Get form data and validate
    fields = {
        "username": request.form.get("username", "").strip(),
        "password": request.form.get("password", ""),
        "first_name": request.form.get("first_name", "").strip(),
        "last_name": request.form.get("last_name", "").strip(),
        "job_title": request.form.get("job_title", "").strip(),
        "level": request.form.get("level", "").strip(),
        "hourly_wage": request.form.get("hourly_wage", request.form.get("hourly_wage", "")).strip(),
    }

    errors = []

    if not fields["username"]:
        errors.append("Username is required.")
    if not fields["password"]:
        errors.append("Password is required.")
    if not fields["first_name"]:
        errors.append("First name is required.")
    elif any(character.isdigit() for character in fields["first_name"]):
        errors.append("First name must not contain numbers.")
    if not fields["last_name"]:
        errors.append("Last name is required.")
    elif any(character.isdigit() for character in fields["last_name"]):
        errors.append("Last name must not contain numbers.")
    if not fields["job_title"]:
        errors.append("Job title is required.")

    level_names = {"Associate": 1, "Manager": 2, "Administrator": 3, "Admin": 3}
    level = level_names.get(fields["level"])
    if level is None or level not in (1, 2, 3):
        errors.append("Please select a valid level.")

    hourly_wage = None
    if fields["hourly_wage"]:
        try:
            hourly_wage = Decimal(fields["hourly_wage"])
            if not hourly_wage.is_finite() or hourly_wage < 0:
                raise InvalidOperation
            if hourly_wage.as_tuple().exponent < -2:
                errors.append("Hourly wage must have no more than 2 digits after the decimal point.")
        except (InvalidOperation, ValueError):
            errors.append("Hourly wage must be a valid number.")
    else:
        errors.append("Hourly wage is required.")

    # If errors, return to registration page with errors and pre-filled fields 
    if errors:
        return render_template(
            "login.html",
            registration_error=" ".join(errors),
            registration_open=True,
            registration=fields,
        ), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Save an existing role, or create one for this new job title.
        role = cursor.execute(
            "SELECT role_id FROM Roles WHERE role_name = ?",
            (fields["job_title"].strip(),),
        ).fetchone()
        if role is None:
            cursor.execute(
                "INSERT INTO Roles (role_name, system_role_id) VALUES (?, ?)",
                (fields["job_title"].strip(), level),
            )
            role_id = cursor.lastrowid
        else:
            role_id = role["role_id"]

        cursor.execute(
            """
            INSERT INTO Employees
            (role_id, first_name, last_name, hourly_wage)
            VALUES (?, ?, ?, ?)
            """,
            (
                role_id,
                fields["first_name"],
                fields["last_name"],
                float(hourly_wage),
            ),
        )
        employee_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO Users
            (username, password, system_role_id, employee_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                fields["username"],
                generate_password_hash(fields["password"]),
                level,
                employee_id,
            ),
        )
        userid = cursor.lastrowid

        conn.commit()
    except sqlite3.IntegrityError as error:
        conn.rollback()
        conn.close()
        return render_template(
            "login.html",
            registration_error=str(error),
            registration_open=True,
            registration=fields,
        ), 400
    finally:
        if conn:
            conn.close()

    session["userid"] = userid
    session["username"] = fields["username"]
    session["system_role_id"] = level
    login_user(User(
        userid=userid,
        username=fields["username"],
        system_role_id=level,
        employee_id=employee_id,
    ))
    return redirect(url_for("dashboard"))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("login"))

@app.route("/level_select", methods=["GET", "POST"])
@login_required
def level_select():
    # Check user logged in
    userid = current_user.userid

    # Get level from form submission
    if request.method == "POST":
        try:
            level = int(request.form["level"])
        except (KeyError, ValueError, TypeError):
            return render_template(
                "level_select.html",
                error="Please select a valid level."
            ), 400

        if level not in (0, 1, 2):
            return render_template(
                "level_select.html",
                error="Please select a valid level."
            ), 400


        conn = get_db_connection()
        conn.execute(
            "UPDATE Users SET system_role_id = ? WHERE userid = ?",
            (level, userid)
        )
        conn.commit()

        updated_level = conn.execute(
            "SELECT system_role_id FROM Users WHERE userid = ?",
            (userid,)
        ).fetchone()
        conn.close()

        if updated_level is None:
            return redirect(url_for("login"))

        if updated_level["system_role_id"] != level or updated_level["system_role_id"] == 0:
            return render_template(
                "level_select.html",
                error="Failed to update level. Please try again."
            ), 500
        
        session["system_role_id"] = level
        current_user.system_role_id = level
        return redirect(url_for("dashboard"))

    return render_template("level_select.html")

# =======================================================
# DASHBOARD ROUTES
# =======================================================

@app.route("/dashboard")
@login_required
def dashboard():
    """ Displays the WorkforceIQ manager dashboard """
    return render_template("dashboard.html")

# =======================================================
# EMPLOYEE MANAGEMENT ROUTES
# =======================================================

@app.route("/employees")
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
            Employees.hourly_wage
        FROM Employees
        LEFT JOIN Roles ON Roles.role_id = Employees.role_id
        """
    )

    # Shows wage of employees based on the current user's access level
    employees = []
    for row in cursor.fetchall():
        employee_id = row["employee_id"]
        account_level = row["system_role_id"]
        hourly_wage = None

        # Admins see all
        if current_user.system_role_id == 3:
            hourly_wage = row["hourly_wage"]
        # Managers see their own wage and Associates wages
        elif current_user.system_role_id == 2:
            if account_level == 1 or employee_id == current_user.employee_id:
                hourly_wage = row["hourly_wage"]
        # Associates only see their own wage
        elif employee_id == current_user.employee_id:
            hourly_wage = row["hourly_wage"]

        # Add data to employees to be put into the table
        employees.append((
            row["first_name"],
            row["last_name"],
            row["role_name"],
            row["account_level"],
            hourly_wage,
        ))

    conn.close()

    return render_template("employees.html", employees=employees, restricted=(current_user.system_role_id == 1))

#TODO: 400 call with errors when adding employee fails, and display errors on the page
@app.route("/add_employee", methods=["POST"])
@login_required
def add_employee():
    first_name = request.form["first_name"].strip()
    last_name = request.form["last_name"].strip()
    role_name = request.form["role_name"].strip()
    level = int(request.form["level"])
    hourly_wage = request.form["wage"].strip()
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
        (role_id, first_name, last_name, hourly_wage)
        VALUES (?, ?, ?, ?)
        """,
        (role_id, first_name, last_name, hourly_wage),
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

    return redirect(url_for("employees"))

# ==========================================================
# FLASK API FOR AI INTEGRATION
# ==========================================================

@app.route("/api/employees")
def api_employees():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT first_name, last_name, role_id, hourly_wage
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
            "hourly_wage": row["hourly_wage"],
        })

    conn.close()
    return jsonify(results)

# =========================================================
# AI ASSISTANT PROTOTYPE
# =========================================================

@app.route("/ai", methods=["GET", "POST"])
@login_required
def ai_assistant():
    response = ""

    if request.method == "POST":
        question = request.form["question"]
        employee_context = get_employee_context()

        prompt = f""" 
        You are WorkforceIQ, an AI workforce scheduling assistant.
        
        Use ONLY the employee information below.

        Do not invent employees.
        Do not invent wages.
        Do not invent roles.
        Do not invent schedules.

        {employee_context}
        
        Question:
        {question}
        """

        response = ask_ollama(prompt)
        
    return render_template("ai_assistant.html", response=response)

@app.route("/forecast")
@login_required
def forecast():

    predicted_demand = generate_forecast()

    recommended_staff = round(predicted_demand / 30)

    return render_template("forecast.html", demand=predicted_demand, staff=recommended_staff)

if __name__ == "__main__":
    app.run(debug=True)
    
