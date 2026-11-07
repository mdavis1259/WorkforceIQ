import sqlite3
from tkinter import LEFT
import requests
import numpy as np
from decimal import Decimal, InvalidOperation
from authentication.AuthService import AuthService
from sklearn.linear_model import LinearRegression
from werkzeug.security import generate_password_hash
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

from database.connection import get_db_connection

from employee_management.EmployeeRoutes import employee_bp
from authentication.AuthRoutes import auth_bp
from user_management.User import User

app = Flask(__name__)
app.register_blueprint(auth_bp)
app.register_blueprint(employee_bp)
app.secret_key = (
    app.config.get("SECRET_KEY")
    or "development-key-change-in-production"
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


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
    
