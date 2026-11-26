"""Routes for the Employee Management module (US-3, SDS section 8.3).

Routes only deal with requests and responses. Business rules and validation
live in EmployeeService.py, and all SQL lives in
EmployeeRepository.py. There is no SQL in this file.

Pages (HTML)
    GET       /employees                    everyone signed in, ?search= to search
    GET       /employees/<id>               managers, or an employee for their own record
    GET/POST  /employees/new                managers
    GET/POST  /employees/<id>/edit          managers
    POST      /employees/<id>/deactivate    managers
    POST      /employees/<id>/reactivate    managers

API (JSON, SDS 8.3)
    GET     /api/employees                  managers (?search= &include_inactive= &page= &page_size=)
    GET     /api/employees/<id>             managers, or an employee for their own record
    POST    /api/employees                  managers
    PUT     /api/employees/<id>             managers
    DELETE  /api/employees/<id>             managers (deactivates, never deletes)
    POST    /api/employees/<id>/reactivate  managers (undoes a deactivation)
    PUT     /api/employees/<id>/qualifications   managers

Every POST/PUT/DELETE must send the CSRF token: an X-CSRF-Token header for the
API, or a hidden csrf_token field in the HTML forms. All API errors use the
single format from SDS 8.8.
"""
import hmac
import secrets
import uuid
from contextlib import contextmanager
from functools import wraps

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, session, url_for)
from flask_login import current_user

from database.connection import get_db_connection
from employee_management.EmployeeRepository import EmployeeRepository
from employee_management.EmployeeService import (DEFAULT_MAX_HOURS,
                                                 DEFAULT_PREFERRED_HOURS,
                                                 EmployeeService)
from shared.exceptions import NotFoundError, ValidationError

employee_bp = Blueprint("employee", __name__, template_folder="templates")

ACCESS_LEVELS = {0: "Unregistered", 1: "Associate", 2: "Manager",
                 3: "Administrator"}
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
FORM_FIELDS = ("first_name", "last_name", "role_id", "hourly_rate",
               "max_hours_per_week", "preferred_hours_per_week")


# ======================================================================
# Helpers
# ======================================================================
@contextmanager
def employee_service():
    """Opens the database, hands back an EmployeeService, always closes it."""
    connection = get_db_connection()
    try:
        yield EmployeeService(EmployeeRepository(connection))
    finally:
        connection.close()


def is_api_request():
    return request.path.startswith("/api/")


def is_manager():
    return current_user.system_role_id >= 2


def api_error(status, code, message, details=None):
    """The single error format from SDS section 8.8."""
    error = {"code": code, "message": message,
             "request_id": uuid.uuid4().hex[:8]}
    if details is not None:
        error["details"] = details
    return jsonify({"error": error}), status


def forbidden(message="You do not have permission to do that."):
    if is_api_request():
        return api_error(403, "FORBIDDEN", message)
    return message, 403


def manager_required(view):
    """Only Managers (level 2) and Administrators (level 3) may continue."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_manager():
            return forbidden()
        return view(*args, **kwargs)
    return wrapper


# ----- CSRF -------------------------------------------------------------
def csrf_token():
    """The signed-in session's CSRF token (created the first time it is needed)."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


def csrf_is_valid():
    expected = session.get("csrf_token", "")
    sent = (request.headers.get("X-CSRF-Token")
            or request.form.get("csrf_token", ""))
    return bool(expected) and hmac.compare_digest(sent.encode(),
                                                  expected.encode())


@employee_bp.app_context_processor
def add_csrf_token_to_templates():
    """Lets any template write {{ csrf_token() }}."""
    return {"csrf_token": csrf_token}


# ----- who may see which wage -------------------------------------------
def can_see_rate(employee, levels):
    """Same wage rule as the original Employees page.

    Administrators see every wage. Managers see Associates' wages and their
    own. Associates see only their own. `levels` maps role_id to access level.
    """
    me = current_user.system_role_id
    if me == 3 or employee.employee_id == current_user.employee_id:
        return True
    return me == 2 and levels.get(employee.role_id) == 1


def lookups(service):
    """Roles and qualifications, plus dictionaries for showing their names."""
    roles = service.list_roles()
    qualifications = service.list_qualifications()
    return {
        "roles": roles,
        "qualifications": qualifications,
        "role_names": {r["role_id"]: r["role_name"] for r in roles},
        "levels": {r["role_id"]: r["system_role_id"] for r in roles},
        "qualification_names": {q["qualification_id"]: q["qualification_name"]
                                for q in qualifications},
    }


def present(employee, look):
    """Turns an Employee into a plain dictionary for the templates."""
    level = look["levels"].get(employee.role_id)
    return {
        "employee_id": employee.employee_id,
        "first_name": employee.first_name,
        "last_name": employee.last_name,
        "role_name": look["role_names"].get(employee.role_id, "-"),
        "access_level": ACCESS_LEVELS.get(level, "-"),
        "max_hours_per_week": employee.max_hours_per_week,
        "preferred_hours_per_week": employee.preferred_hours_per_week,
        "active": employee.active,
        "qualifications": [look["qualification_names"][i]
                           for i in employee.qualification_ids
                           if i in look["qualification_names"]],
        "hourly_rate": (employee.hourly_rate
                        if can_see_rate(employee, look["levels"]) else None),
        "can_view": (is_manager()
                     or employee.employee_id == current_user.employee_id),
    }


# ----- reading requests ---------------------------------------------------
def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError([{
            "field": "body",
            "issue": "Request body must be a JSON object."}])
    return data


def read_paging():
    """?page=1&page_size=25 (maximum 100), SDS section 8.1."""
    problems = []

    def number(name, default, low, high):
        raw = request.args.get(name)
        if raw is None or raw == "":
            return default
        try:
            value = int(raw)
        except ValueError:
            value = None
        if value is None or not low <= value <= high:
            problems.append({
                "field": name,
                "issue": f"Must be a whole number from {low} to {high}."})
            return default
        return value

    page = number("page", 1, 1, 1_000_000)
    page_size = number("page_size", DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
    if problems:
        raise ValidationError(problems)
    return page, page_size


def read_form():
    """Employee fields from an HTML form, as strings. The service checks them."""
    data = {field: request.form.get(field, "") for field in FORM_FIELDS}
    data["qualification_ids"] = request.form.getlist("qualification_ids")
    return data


def render_employee_form(look, values, employee=None, errors=None,
                         can_edit_rate=True, status=200):
    """Shows the add/edit form again, with the errors beside each field."""
    field_errors = {}
    for problem in errors or []:
        field_errors.setdefault(problem["field"], []).append(problem["issue"])
    selected = {str(i) for i in values.get("qualification_ids", [])}
    html = render_template(
        "employee_form.html",
        roles=look["roles"],
        qualifications=look["qualifications"],
        values=values,
        selected_qualifications=selected,
        field_errors=field_errors,
        employee=employee,
        can_edit_rate=can_edit_rate,
    )
    return html, status


# ======================================================================
# Checks that run before every route in this file
# ======================================================================
@employee_bp.before_request
def check_access():
    """Signed in? Allowed in? Valid CSRF token on a change?"""
    if not current_user.is_authenticated:
        if is_api_request():
            return api_error(401, "UNAUTHENTICATED", "Please sign in.")
        return current_app.login_manager.unauthorized()
    if current_user.system_role_id < 1:
        return forbidden("Your account does not have access yet.")
    if (request.method in ("POST", "PUT", "PATCH", "DELETE")
            and not csrf_is_valid()):
        if is_api_request():
            return api_error(403, "CSRF_FAILED",
                             "Missing or invalid CSRF token.")
        return ("Missing or invalid security token. "
                "Reload the page and try again."), 403


@employee_bp.errorhandler(NotFoundError)
def handle_not_found(error):
    if is_api_request():
        return api_error(404, "NOT_FOUND", str(error))
    return str(error), 404


@employee_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    if is_api_request():
        return api_error(400, "VALIDATION_ERROR",
                         "One or more fields are invalid.", error.details)
    return str(error), 400


# ======================================================================
# Pages
# ======================================================================
@employee_bp.route("/employees")
def employees():
    """The employee table with search. Managers also see add/edit links."""
    search = request.args.get("search", "").strip()
    show_inactive = is_manager() and request.args.get("show_inactive") == "1"
    with employee_service() as service:
        found = service.list_employees(search=search,
                                       include_inactive=show_inactive)
        look = lookups(service)
    return render_template(
        "employees.html",
        employees=[present(employee, look) for employee in found],
        search=search,
        show_inactive=show_inactive,
        is_manager=is_manager(),
    )


@employee_bp.route("/employees/new", methods=["GET", "POST"])
@manager_required
def new_employee():
    with employee_service() as service:
        look = lookups(service)
        if request.method == "POST":
            values = read_form()
            try:
                employee = service.create_employee(values)
            except ValidationError as error:
                return render_employee_form(look, values,
                                            errors=error.details, status=400)
            flash(f"{employee.first_name} {employee.last_name} was added.",
                  "success")
            return redirect(url_for("employee.employee_detail",
                                    employee_id=employee.employee_id))
    values = {"max_hours_per_week": DEFAULT_MAX_HOURS,
              "preferred_hours_per_week": DEFAULT_PREFERRED_HOURS,
              "qualification_ids": []}
    return render_employee_form(look, values)


@employee_bp.route("/employees/<int:employee_id>")
def employee_detail(employee_id):
    if not is_manager() and employee_id != current_user.employee_id:
        return forbidden()
    with employee_service() as service:
        employee = service.get_employee(employee_id)
        look = lookups(service)
    return render_template("employee_detail.html",
                           employee=present(employee, look),
                           is_manager=is_manager())


@employee_bp.route("/employees/<int:employee_id>/edit",
                   methods=["GET", "POST"])
@manager_required
def edit_employee(employee_id):
    with employee_service() as service:
        look = lookups(service)
        current = service.get_employee(employee_id)  # 404 if missing
        can_edit_rate = can_see_rate(current, look["levels"])

        if request.method == "POST":
            values = read_form()
            if not can_edit_rate:
                # Nobody may change a wage they are not allowed to see.
                values["hourly_rate"] = current.hourly_rate
            try:
                service.update_employee(employee_id, values)
            except ValidationError as error:
                return render_employee_form(
                    look, values, employee=present(current, look),
                    errors=error.details, can_edit_rate=can_edit_rate,
                    status=400)
            flash("Changes saved.", "success")
            return redirect(url_for("employee.employee_detail",
                                    employee_id=employee_id))

        values = {
            "first_name": current.first_name,
            "last_name": current.last_name,
            "role_id": current.role_id,
            "hourly_rate": current.hourly_rate if can_edit_rate else "",
            "max_hours_per_week": current.max_hours_per_week,
            "preferred_hours_per_week": current.preferred_hours_per_week,
            "qualification_ids": list(current.qualification_ids),
        }
        return render_employee_form(look, values,
                                    employee=present(current, look),
                                    can_edit_rate=can_edit_rate)


@employee_bp.route("/employees/<int:employee_id>/deactivate",
                   methods=["POST"])
@manager_required
def deactivate_employee_page(employee_id):
    with employee_service() as service:
        employee = service.get_employee(employee_id)  # 404 if missing
        service.deactivate_employee(employee_id)
    flash(f"{employee.first_name} {employee.last_name} was deactivated.",
          "success")
    return redirect(url_for("employee.employees"))


@employee_bp.route("/employees/<int:employee_id>/reactivate",
                   methods=["POST"])
@manager_required
def reactivate_employee_page(employee_id):
    with employee_service() as service:
        employee = service.reactivate_employee(employee_id)  # 404 if missing
    flash(f"{employee.first_name} {employee.last_name} was reactivated.",
          "success")
    return redirect(url_for("employee.employee_detail",
                            employee_id=employee_id))


# ======================================================================
# JSON API (SDS 8.3)
# ======================================================================
@employee_bp.route("/api/employees", methods=["GET"])
@manager_required
def api_list_employees():
    page, page_size = read_paging()
    search = request.args.get("search", "")
    include_inactive = request.args.get("include_inactive", "").lower() in (
        "1", "true", "yes")
    with employee_service() as service:
        found = service.list_employees(search=search,
                                       include_inactive=include_inactive)
        levels = lookups(service)["levels"]
    start = (page - 1) * page_size
    items = [employee.to_dict(include_rate=can_see_rate(employee, levels))
             for employee in found[start:start + page_size]]
    return jsonify({"items": items, "page": page, "page_size": page_size,
                    "total": len(found)})


@employee_bp.route("/api/employees/<int:employee_id>", methods=["GET"])
def api_get_employee(employee_id):
    if not is_manager() and employee_id != current_user.employee_id:
        return forbidden()
    with employee_service() as service:
        employee = service.get_employee(employee_id)
        levels = lookups(service)["levels"]
    return jsonify(employee.to_dict(
        include_rate=can_see_rate(employee, levels)))


@employee_bp.route("/api/employees", methods=["POST"])
@manager_required
def api_create_employee():
    data = json_body()
    with employee_service() as service:
        employee = service.create_employee(data)
        levels = lookups(service)["levels"]
    return jsonify(employee.to_dict(
        include_rate=can_see_rate(employee, levels))), 201


@employee_bp.route("/api/employees/<int:employee_id>", methods=["PUT"])
@manager_required
def api_update_employee(employee_id):
    data = json_body()
    with employee_service() as service:
        current = service.get_employee(employee_id)  # 404 if missing
        levels = lookups(service)["levels"]
        if not can_see_rate(current, levels):
            data["hourly_rate"] = current.hourly_rate  # wage stays as it was
        # Hours that were left out keep their current values.
        data.setdefault("max_hours_per_week", current.max_hours_per_week)
        data.setdefault("preferred_hours_per_week",
                        current.preferred_hours_per_week)
        employee = service.update_employee(employee_id, data)
    return jsonify(employee.to_dict(
        include_rate=can_see_rate(employee, levels)))


@employee_bp.route("/api/employees/<int:employee_id>", methods=["DELETE"])
@manager_required
def api_deactivate_employee(employee_id):
    with employee_service() as service:
        service.deactivate_employee(employee_id)
    return "", 204


@employee_bp.route("/api/employees/<int:employee_id>/reactivate",
                   methods=["POST"])
@manager_required
def api_reactivate_employee(employee_id):
    with employee_service() as service:
        employee = service.reactivate_employee(employee_id)
        levels = lookups(service)["levels"]
    return jsonify(employee.to_dict(
        include_rate=can_see_rate(employee, levels)))


@employee_bp.route("/api/employees/<int:employee_id>/qualifications",
                   methods=["PUT"])
@manager_required
def api_set_qualifications(employee_id):
    data = json_body()
    if "qualification_ids" not in data:
        raise ValidationError([{
            "field": "qualification_ids",
            "issue": "qualification_ids is required (use [] for none)."}])
    with employee_service() as service:
        employee = service.set_qualifications(employee_id,
                                              data["qualification_ids"])
        levels = lookups(service)["levels"]
    return jsonify(employee.to_dict(
        include_rate=can_see_rate(employee, levels)))
