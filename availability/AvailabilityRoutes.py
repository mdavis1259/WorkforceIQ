from contextlib import contextmanager
import hmac
import secrets
import uuid

from flask import (
    Blueprint,
    render_template,
    jsonify,
    redirect,
    request,
    session,
    url_for
)
from functools import wraps

from flask_login import current_user, login_required
from availability import Availability
from database.connection import get_db_connection
from availability.AvailabilityRepository import AvailabilityRepository
from availability.AvailabilityService import AvailabilityService
from employee_management.EmployeeRepository import EmployeeRepository
from employee_management.EmployeeRoutes import manager_required
from employee_management.EmployeeService import Employee, EmployeeService
from dataclasses import asdict

from shared.exceptions import ValidationError, NotFoundError
from datetime import datetime

availability_bp = Blueprint(
    'availability',
    __name__,
    template_folder='templates'
)

# ==============================================
# Helper functions
# ==============================================
@contextmanager
def _build_availability_service(conn):
    """Build repository and service instances."""
    employee_repo = EmployeeRepository(conn)
    employee_service = EmployeeService(employee_repo)

    availability_repo = AvailabilityRepository(conn)
    service = AvailabilityService(availability_repo, employee_service)
    try:
        yield service
    finally:
        conn.close()

def _is_api_request():
    """Determine if the current request is an API request."""
    return request.path.startswith("/api/")

def _is_manager():
    """Check if the current user is a manager or higher."""
    return current_user.system_role_id >= 2

def _forbidden(message="You do not have permission to do that."):
    """Return a forbidden response, formatted for API or web requests."""
    if _is_api_request():
        return _api_error(403, "FORBIDDEN", message)
    return message, 403

def _json_body():
    """Parse JSON request body, raising ValidationError if invalid."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")
    return data

def manager_required(view):
    """Only Managers (level 2) and Administrators (level 3) may continue."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not _is_manager():
            return _forbidden()
        return view(*args, **kwargs)
    return wrapper

def _api_error(status, code, message, details=None):
    """Standardized API error response format from SDS Section 8.8"""
    error = {"code": code, "message": message,
             "request_id": uuid.uuid4().hex[:8]}
    if details is not None:
        error["details"] = details
    return jsonify({"error": error}), status

# ==============================================
# CSRF
# ==============================================

def csrf_token():
    """The signed-in session's CSRF token (created the first time it is needed)."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


def csrf_is_valid():
    """Validate the CSRF token for the current request."""
    expected = session.get("csrf_token", "")
    sent = (request.headers.get("X-CSRF-Token")
            or request.form.get("csrf_token", ""))
    return bool(expected) and hmac.compare_digest(sent.encode(),
                                                  expected.encode())

@availability_bp.app_context_processor
def add_csrf_token_to_templates():
    """Add the CSRF token to the template context."""
    return {"csrf_token": csrf_token()}

# ==============================================
# HTML Routes
# ==============================================

@availability_bp.route('/availability', methods=["GET"])
@login_required
def availability_selector():
    """Show employee selector for managers/admins, or redirect employees to their own availability."""
    # Redirect employees to their own availability page
    if current_user.system_role_id == 1:
        return redirect(url_for("availability.availability_detail",
                                employee_id=current_user.employee_id))
    conn = get_db_connection()
    with _build_availability_service(conn) as service:
        # List employees that the current user can select for availability management
        selectable_employees = service.get_selectable_employees(current_user)

        return render_template(
            'avail_select.html',
            employees=selectable_employees,
        )

@availability_bp.route('/availability/<int:employee_id>', methods=["GET", "POST"])
@login_required
def availability_detail(employee_id):
    """Display and manage availability for a specific employee."""
    conn = get_db_connection()
    with _build_availability_service(conn) as service:
        employee = service.employee_service.get_employee(employee_id)
        if not service.user_can_access_employee(current_user, employee):
            return _forbidden()

        # Throws NotFoundError if the employee does not exist
        employee = service.employee_service.get_employee(employee_id)

        if request.method == "POST":
            try:
                data = _json_body()
            except ValidationError as error:
                return _api_error(400, "VALIDATION_ERROR", str(error))

            updated = service.update_availability(data, employee_id)
            if not updated:
                raise NotFoundError("Availability not found")

            return jsonify({"status": "success", "id": updated, "message": "Availability updated successfully"}), 200

        time_off_objects = service.get_time_off_by_employee(employee_id)
        avail_events, background_events, approved_days = service.availability_db_to_events(
            service.get_availability_by_employee(employee_id),
            time_off_objects,
            employee_id,
        )
        can_review = current_user.system_role_id in (2, 3) and employee_id != current_user.employee_id
        pending_ids = {time_off.request_id for time_off in time_off_objects if time_off.status == "Pending"}
        calendar_background_events = [
            {**segment, "reviewRequestId": event["id"]}
            if can_review and event["id"] in pending_ids else segment
            for event in background_events
            for segment in service.split_background_event(event)
        ]
        return render_template('availability.html',
                                availability=avail_events,
                                background=calendar_background_events,
                                can_review=can_review,
                                approved_days=approved_days,
                                time_off_ranges=[
                                    {
                                        "start": time_off.start_date[:10],
                                        "end": time_off.end_date[:10],
                                    }
                                    for time_off in time_off_objects
                                    if time_off.status != "Cancelled"
                                ],
                                employee=employee)

# ==========================================
# API Routes
# ==========================================

# Gets weekly availabiltiy for an employee
@availability_bp.route('/api/employees/<int:employee_id>/availability', methods=["GET"])
@login_required
def get_employee_availability(employee_id):
    """Get weekly availability for an employee."""
    employee = service.employee_service.get_employee(employee_id)
    if not service.user_can_access_employee(current_user, employee):
        return _api_error(403, "FORBIDDEN", "You are not allowed to view this employee's availability")

    conn = get_db_connection()
    try:
        with _build_availability_service(conn) as service:
            employee = service.employee_service.get_employee(employee_id)
            if employee is None:
                return _api_error(404, "NOT_FOUND", f"Employee {employee_id} not found")

            weekly_grid = service.get_weekly_grid(employee_id)
            if not weekly_grid or len(weekly_grid) == 0:
                return _api_error(404, "NOT_FOUND", "No availability found for this employee")
            if not service.user_can_access_employee(current_user, employee):
                return _api_error(403, "FORBIDDEN", "You are not allowed to view this employee's availability")

            weekly_list = []
            for avail in weekly_grid:
                if avail is None or type(avail) is not Availability:
                    return _api_error(400, "INVALID_STATE", "Availability object is invalid")
                weekly_list.append(asdict(avail))

            return jsonify({"weekly_grid": weekly_list}), 200
    except Exception as e:
        return _api_error(400, "ERROR", str(e))
    finally:
        conn.close()

# Replace weekly availability grid for an employee
@availability_bp.route('/api/employees/<int:employee_id>/availability', methods=["PUT"])
@login_required
def update_employee_availability(employee_id):
    """
    Replace the entire weekly availability grid for an employee.
    Employees can only update their own. Managers can update employees. Admin can update anyone.
    Request body: {"entries": [{"workday_id": 1, "shift_id": 1, "available": true}, ...]}
    """
    employee = service.employee_service.get_employee(employee_id)
    if not service.user_can_access_employee(current_user, employee):
        return _api_error(403, "FORBIDDEN", "You are not allowed to update this employee's availability")

    conn = get_db_connection()
    try:
        with _build_availability_service(conn) as service:
            employee = service.employee_service.get_employee(employee_id)
            if employee is None:
                return _api_error(404, "NOT_FOUND", f"Employee {employee_id} not found")

            try:
                data_json = _json_body()
            except ValidationError as error:
                return _api_error(400, "VALIDATION_ERROR", str(error))

            weekly_grid = data_json.get("weekly_grid")
            if not isinstance(weekly_grid, list):
                return _api_error(400, "VALIDATION_ERROR", "weekly_grid must be a list")

            for avail_dict in weekly_grid:
                if not isinstance(avail_dict, dict):
                    return _api_error(400, "VALIDATION_ERROR", "Each entry must be an object")
                if "workday_id" not in avail_dict or "shift_id" not in avail_dict or "available" not in avail_dict:
                    return _api_error(400, "VALIDATION_ERROR", "Each entry must have workday_id, shift_id, and available")
                if not isinstance(avail_dict["available"], bool):
                    return _api_error(400, "VALIDATION_ERROR", "available must be a boolean")

            availability = service.replace_weekly_grid(employee_id, weekly_grid)
            avail_list = []
            for avail in availability:
                if avail is None or type(avail) is not Availability:
                    return _api_error(400, "INVALID_STATE", "Availability object is invalid")
                avail_list.append(asdict(avail))

            return jsonify({"weekly_grid": avail_list}), 200

    except (AttributeError, KeyError, TypeError) as e:
        return _api_error(400, "VALIDATION_ERROR", str(e))
    finally:
        conn.close()

# List who is available for a date and shift
# Query params: date (string, YYYY-MM-DD), shift_id (integer, exists)
@availability_bp.route('/api/availability?date=<string:date>&shift_id=<int:shift_id>', methods=["GET"])
@login_required
@manager_required
def get_employees_by_date_and_shift(date, shift_id):
    """List who is available for a date and shift."""
    if not date or type(date) is not str:
        return _api_error(400, "VALIDATION_ERROR", "Date string required")
    try:
        datetime_obj = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return _api_error(400, "VALIDATION_ERROR", "Invalid date format")

    if not shift_id:
        return _api_error(400, "VALIDATION_ERROR", "shift_id required")
    try:
        shift_id = int(shift_id)
        if shift_id <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return _api_error(400, "VALIDATION_ERROR", "Invalid date or shift_id format")

    conn = get_db_connection()
    try:
        with _build_availability_service(conn) as service:
            workday_id = datetime_obj.isoweekday()

            available_employees = service.get_available_employees_for_shift(workday_id, shift_id)
            if not available_employees:
                return _api_error(404, "NOT_FOUND", "No available employees found for that shift on that date")

            emp_list = []
            for emp in available_employees:
                if emp is None or type(emp) is not Employee:
                    return _api_error(400, "INVALID_STATE", "Employee object is invalid")
                emp_list.append(asdict(emp))

            return jsonify({
                "date": date,
                "shift_id": shift_id,
                "count": len(available_employees),
                "employees": emp_list
            }), 200
    finally:
        conn.close()

@availability_bp.route('/api/time-off-requests', methods=["POST"])
@login_required
def create_time_off_request():
    conn = get_db_connection()
    try:
        with _build_availability_service(conn) as service:
            try:
                data = _json_body()
            except ValidationError as error:
                return _api_error(400, "VALIDATION_ERROR", str(error))

            event = service.create_time_off_request(data, current_user.employee_id)
            return jsonify({
                "status": "success",
                "event": event,
            }), 201
    finally:
        conn.close()

# UNCHECKED TODO
@availability_bp.route('/api/time-off-requests/<int:request_id>', methods=["GET", "PUT"])
@login_required
def review_time_off_request(request_id):
    if current_user.system_role_id not in (2, 3):
        return _api_error(403, "FORBIDDEN", "Not authorized to review requests")
    
    conn = get_db_connection()
    try:
        with _build_availability_service(conn) as service:
            time_off = service.availability_repository.get_time_off_request_by_id(request_id)
            if time_off is None:
                return _api_error(404, "NOT_FOUND", "Time-off request not found")
            
            employee_id = time_off.employee_id
            if employee_id == current_user.employee_id:
                return _api_error(403, "FORBIDDEN", "Cannot review your own requests")

            if request.method == "GET":
                review = service.get_time_off_review(request_id, employee_id)
                if review is None:
                    return _api_error(404, "NOT_FOUND", "Time-off request not found")
                return jsonify({"status": "success", "request": review})

            if time_off.status != "Pending":
                return _api_error(409, "CONFLICT", "Time-off request is no longer pending")

            try:
                data = _json_body()
            except ValidationError as error:
                return _api_error(400, "VALIDATION_ERROR", str(error))

            try:
                updated = service.review_time_off_request(request_id, employee_id, data)
            except ValueError as error:
                return _api_error(400, "VALIDATION_ERROR", str(error))

            if not updated:
                return _api_error(409, "CONFLICT", "Time-off request is no longer pending")

            _, _, approved_days = service.availability_db_to_events(
                [], service.get_time_off_by_employee(employee_id), employee_id
            )
            row = service.get_time_off_request(request_id, employee_id)
            event = service.time_off_event(row)
            return jsonify({
                "status": "success",
                "background_events": service.split_background_event(event),
                "approved_days": approved_days,
            })
    finally:
        conn.close()

@availability_bp.route('/api/time-off-requests', methods=["GET"])
@login_required
def get_time_off_requests():
    """
    List time-off requests.
    Employees see only their own. Managers see all.
    """
    conn = get_db_connection()
    try:
        with _build_availability_service(conn) as service:
            if current_user.system_role_id == 1:
                requests = service.get_time_off_by_employee(current_user.employee_id)
            else:
                requests = service.get_all_time_off_requests()

            return jsonify({
                "requests": [
                    {
                        "request_id": r.request_id,
                        "employee_id": r.employee_id,
                        "start_date": r.start_date,
                        "end_date": r.end_date,
                        "status": r.status
                    }
                    for r in requests
                ]
            }), 200
    except Exception as e:
        return _api_error(400, "ERROR", str(e))
    finally:
        conn.close()

@availability_bp.route('/api/time-off-requests/<int:request_id>', methods=["PATCH"])
@login_required
def patch_time_off_request(request_id):
    """
    Approve, deny, or cancel a time-off request.
    Managers can approve/deny. Owners can cancel.
    Request body: {"action": "approve" | "deny" | "cancel"}
    """
    conn = get_db_connection()
    try:
        with _build_availability_service(conn) as service:
            try:
                data = _json_body()
            except ValidationError as error:
                return _api_error(400, "VALIDATION_ERROR", str(error))

            action = data.get("action")
            if action not in ("approve", "deny", "cancel"):
                return _api_error(400, "VALIDATION_ERROR", "action must be 'approve', 'deny', or 'cancel'")

            time_off = service.availability_repository.get_time_off_request_by_id(request_id)
            if time_off is None:
                return _api_error(404, "NOT_FOUND", "Time-off request not found")

            if action == "cancel":
                if current_user.employee_id != time_off.employee_id:
                    return _api_error(403, "FORBIDDEN", "Only the request owner can cancel")
            else:
                if current_user.system_role_id < 2:
                    return _api_error(403, "FORBIDDEN", "Only managers can approve or deny requests")

            try:
                new_status = "Approved" if action == "approve" else "Denied" if action == "deny" else "Cancelled"
                service.update_time_off_request_status(request_id, time_off.employee_id, new_status)
            except ValueError as error:
                return _api_error(409, "CONFLICT", str(error))

            return jsonify({
                "status": "success",
                "message": f"Request {action}ed successfully",
                "new_status": new_status
            }), 200
    except Exception as e:
        return _api_error(400, "ERROR", str(e))
    finally:
        conn.close()