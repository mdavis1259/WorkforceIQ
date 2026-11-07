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

from database.connection import get_db_connection

from employee_management.EmployeeManagementRoutes import employee_bp


app = Flask(__name__)
app.register_blueprint(employee_bp)
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



def get_employee_context():
    employees = requests.get("http://127.0.0.1:5000/api/employees").json()
    context = "Current Employees:\n\n"
    for employee in employees:
        context += (
            f"Name: {employee['first_name'].strip() + ' ' + employee['last_name'].strip()}, "
            f"Role: {employee['role']}, "
            f"Wage: ${employee['hourly_rate']}/hr\n"
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
        "hourly_rate": request.form.get("hourly_rate", request.form.get("hourly_rate", "")).strip(),
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

    hourly_rate = None
    if fields["hourly_rate"]:
        try:
            hourly_rate = Decimal(fields["hourly_rate"])
            if not hourly_rate.is_finite() or hourly_rate < 0:
                raise InvalidOperation
            if hourly_rate.as_tuple().exponent < -2:
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
            (role_id, first_name, last_name, hourly_rate)
            VALUES (?, ?, ?, ?)
            """,
            (
                role_id,
                fields["first_name"],
                fields["last_name"],
                float(hourly_rate),
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
    return render_template("dashboard.html", level = current_user.system_role_id)

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
    
