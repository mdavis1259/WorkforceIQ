import sqlite3
import requests
import numpy as np
from auth import authenticate_user
from sklearn.linear_model import LinearRegression
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

# ======================================================
# HELPER FUNCTIONS
# ======================================================

def get_db_connection():
    return sqlite3.connect("database/workforce.db")

def get_employee_context():
    employees = requests.get("http://127.0.0.1:5000/api/employees").json()
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
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()
        
        user = authenticate_user(username, password, conn)

        if user:
            return redirect(url_for("dashboard"))

	error = "Invalid username or password."
        
    return render_template("login.html", error=error)

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
        "SELECT id, name, role, wage FROM employees"
    )

    employees = cursor.fetchall()

    conn.close()

    return render_template("employees.html", employees=employees)

@app.route("/add_employee", methods=["POST"])
def add_employee():
    name = request.form["name"]
    role = request.form["role"]
    wage = request.form["wage"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
                   INSERT INTO employees
                   (name, role, wage)
                   VALUES (?, ?, ?)
                   """, (name, role, wage)
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
        FROM employees
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
    
