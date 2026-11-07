from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
)

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,   
)

from decimal import Decimal, InvalidOperation
import sqlite3

from database.connection import get_db_connection
from user_management.UserService import UserService
from user_management.UserRepository import UserRepository
from authentication.AuthService import AuthService
from authentication.AuthRepository import AuthRepository
from werkzeug.security import generate_password_hash

from user_management.User import User

auth_bp = Blueprint (
    "auth",
    __name__,
    template_folder="templates"
)

@auth_bp.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("auth.login"))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()

        try:
            user_repository = UserRepository(conn)
            user_service = UserService(user_repository)
            auth_service = AuthService(user_service)
            user = auth_service.authenticate(username, password)
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
                return redirect(url_for("auth.level_select"))

            # Else, go to dashboard
            return redirect(url_for("dashboard"))

        error = "Invalid username or password."
        
    return render_template("login.html", error=error)

# Registration for new users.
@auth_bp.route("/register", methods=["POST"])

# TODO:
# Registration workflow currently spans:
# Authentication
# User Management
# Employee Management
#
# Refactor into:
# UserService/UserRepository
# EmployeeService/EmployeeRepository
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

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/level_select", methods=["GET", "POST"])
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
            return redirect(url_for("auth.login"))

        if updated_level["system_role_id"] != level or updated_level["system_role_id"] == 0:
            return render_template(
                "level_select.html",
                error="Failed to update level. Please try again."
            ), 500
        
        session["system_role_id"] = level
        current_user.system_role_id = level
        return redirect(url_for("dashboard"))

    return render_template("level_select.html")
