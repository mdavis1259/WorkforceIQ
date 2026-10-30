import sqlite3
import requests
import numpy as np
from decimal import Decimal, InvalidOperation
from auth import authenticate_user
from sklearn.linear_model import LinearRegression
from werkzeug.security import generate_password_hash
from flask import Flask, render_template, request, redirect, url_for, jsonify, session

app = Flask(__name__)
app.secret_key = (
    app.config.get("SECRET_KEY")
    or "development-key-change-in-production"
)

# ======================================================
# HELPER FUNCTIONS
# ======================================================

def get_db_connection():
    #Uses regular database by default, but can be overridden for testing
    database = app.config.get("DATABASE", "database/workforce.db") 
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row #Lets us access columns by name instead of index
    return connection

# Split for testing purposes
def get_employees_json():
    return requests.get("http://127.0.0.1:5000/api/employees").json()

def get_employee_context():
    employees = get_employees_json()
    context = "Current Employees:\n\n"
    for employee in employees:
        context += (
            f"Name: {employee['name']}, "
            f"Role: {employee['role']}, "
            f"Wage: ${employee['wage']}/hr\n"
        )
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
# AUTHENTICATION ROUTES
# =====================================================

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
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
            #Save login data to session
            session["userid"] = user["userid"]
            session["username"] = user["username"]
            session["level"] = user["level"]

            #User sets own level
            if user["level"] == 0:
                return redirect(url_for("levelselect"))

            #else, go to dashboard
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
        "wage": request.form.get("wage", "").strip(),
    }

    errors = []
    for field_name, label in (
        ("username", "Username"),
        ("password", "Password"),
        ("first_name", "First name"),
        ("last_name", "Last name"),
        ("job_title", "Job title"),
        ("level", "Job level"),
        ("wage", "Wage"),
    ):
        # Throw error if any field is missing
        if not fields[field_name]:
            errors.append(f"{label} is required.")

    if fields["first_name"] and any(character.isdigit() for character in fields["first_name"]):
        errors.append("First name must not contain numbers.")
    if fields["last_name"] and any(character.isdigit() for character in fields["last_name"]):
        errors.append("Last name must not contain numbers.")

    level_map = {"Associate": 1, "Manager": 2, "Administrator": 3}
    level = level_map.get(fields["level"])
    if fields["level"] and level is None:
        errors.append("Job level must be Associate, Manager, or Administrator.")

    wage = None
    if fields["wage"]:
        try:
            wage = Decimal(fields["wage"])
            if not wage.is_finite() or wage < 0:
                raise InvalidOperation
            if wage.as_tuple().exponent < -2:
                errors.append("Wage must have no more than 2 digits after the decimal.")
        except (InvalidOperation, ValueError):
            errors.append("Wage must be a valid number.")

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
        cursor.execute(
            "INSERT INTO Users(username, password, level) VALUES (?, ?, ?)",
            (
                fields["username"],
                generate_password_hash(fields["password"]),
                level,
            ),
        )
        userid = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO Employees(name, role, wage, userid)
            VALUES (?, ?, ?, ?)
            """,
            (
                f"{fields['first_name']} {fields['last_name']}",
                fields["job_title"],
                float(wage),
                userid,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return render_template(
            "login.html",
            registration_error="Username is already in use.",
            registration_open=True,
            registration=fields,
        ), 400
    finally:
        conn.close()

    session["userid"] = userid
    session["username"] = fields["username"]
    session["level"] = level
    return redirect(url_for("dashboard"))

@app.route("/levelselect", methods=["GET", "POST"])
def levelselect():
    # Check user logged in
    userid = session.get("userid")
    if userid is None:
        return redirect(url_for("login"))

    # Get level from form submission
    if request.method == "POST":
        try:
            level = int(request.form["level"])
        except (KeyError, ValueError, TypeError):
            return render_template(
                "levelselect.html",
                error="Please select a valid level."
            ), 400

        if level not in (0, 1, 2):
            return render_template(
                "levelselect.html",
                error="Please select a valid level."
            ), 400


        conn = get_db_connection()
        conn.execute(
            "UPDATE Users SET level = ? WHERE userid = ?",
            (level, userid)
        )
        conn.commit()

        updated_level = conn.execute(
            "SELECT level FROM Users WHERE userid = ?",
            (userid,)
        ).fetchone()
        conn.close()

        if updated_level is None:
            return redirect(url_for("login"))

        if updated_level["level"] != level or updated_level["level"] == 0:
            return render_template(
                "levelselect.html",
                error="Failed to update level. Please try again."
            ), 500
        
        session["level"] = level
        return redirect(url_for("dashboard"))

    return render_template("levelselect.html")

# =======================================================
# DASHBOARD ROUTES
# =======================================================

@app.route("/dashboard")
def dashboard():
    """ Displays the WorkforceIQ manager dashboard """
    return render_template("dashboard.html")

# =======================================================
# EMPLOYEE MANAGEMENT ROUTES
# =======================================================

@app.route("/employees")
def employees():
    """ Displays a table with employee information """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            Employees.id,
            Employees.name,
            Employees.role,
            Employees.wage,
            CASE
                WHEN Users.level = 0 THEN 'Undefined'
                WHEN Users.level = 1 THEN 'Associate'
                WHEN Users.level = 2 THEN 'Manager'
                WHEN Users.level = 3 THEN 'Administrator'
                ELSE 'Undefined'
            END AS level_name
        FROM Employees
        LEFT JOIN Users ON Users.userid = Employees.userid
        """
    )

    employees = cursor.fetchall()

    conn.close()

    return render_template("employees.html", employees=employees)

@app.route("/add_employee", methods=["POST"])
def add_employee():
    name = request.form["name"]
    role = request.form["role"]
    wage = request.form["wage"]
    username = request.form.get("username", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    userid = None
    if username:
        user = cursor.execute(
            "SELECT userid FROM Users WHERE username = ?",
            (username,),
        ).fetchone()
        if user:
            userid = user["userid"]

    cursor.execute("""
                   INSERT INTO Employees
                   (name, role, wage, userid)
                   VALUES (?, ?, ?, ?)
                   """, (name, role, wage, userid)
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
        SELECT
            name,
            role,
            wage
        FROM Employees
    """)

    data = cursor.fetchall()

    conn.close()
    results = []
    for row in data:
        results.append({
            "name": row[0],
            "role": row[1],
            "wage": row[2]
        })        
    
    return jsonify(results)

# =========================================================
# AI ASSISTANT PROTOTYPE
# =========================================================

@app.route("/ai", methods=["GET", "POST"])
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
def forecast():

    predicted_demand = generate_forecast()

    recommended_staff = round(predicted_demand / 30)

    return render_template("forecast.html", demand=predicted_demand, staff=recommended_staff)

if __name__ == "__main__":
    app.run(debug=True)
    
