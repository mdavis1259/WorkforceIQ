"""
Routes for the Availability Management system (US-4, US-13, US-17).

Routes only deal with requests and responses. Business rules and validation
live in AvailabilityService.py, and all SQL lives in
AvailabilityRepository.py. There is no SQL in this file.

Pages (HTML)
    GET    /availability                                        Employees see own, managers see selector
    GET    /availability/<employee_id>                          Employees see own, managers see other employees
    POST   /availability/<employee_id>                          Employees update own, managers update others

API (JSON, SDS 8.3)
    GET    /api/employees/<employee_id>/availability            Employees get own, managers get others
    PUT    /api/employees/<employee_id>/availability            Employees update own, managers update others
    GET    /api/availability?date=<date>&shift_id=<shift_id>    Manager only
    POST   /api/time-off-requests                               All submit own requests
    GET    /api/time-off-requests                               Manager sees all employees they mannage, employees see own
    PATCH  /api/time-off-requests/<request_id>                  Manager only

Every POST/PUT/DELETE must send the CSRF token: an X-CSRF-Token header for the
API, or a hidden csrf_token field in the HTML forms. All API errors use the
single format from SDS 8.8.   
"""

from contextlib import contextmanager
import hmac
import secrets
from sqlite3 import InternalError
import uuid

from flask import (
    Blueprint,
    current_app,
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
from employee_management.EmployeeService import Employee, EmployeeService
from dataclasses import asdict

from shared.exceptions import InvalidStateError, ValidationError, NotFoundError, ConflictError
from datetime import datetime

availability_bp = Blueprint(
    'availability',
    __name__,
    template_folder='templates'
)

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

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
        raise ValidationError([{"field": "body", "issue": "must be a JSON object"}])
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

@availability_bp.before_request
def check_csrf():
    """Checks signed in, allowed in, and valid CSRF"""
    if not current_user.is_authenticated:
        if _is_api_request():
            return _api_error(401, "UNATHENTICATED", "User is not authenticated.")
        return current_app.login_manager.unauthorized()
    if current_user.system_role_id not in [1, 2, 3]:
        return _forbidden("Account not given access yet.")
    if request.method in ("POST", "PATCH", "PUT", "DELETE") \
        and not csrf_is_valid():
        if _is_api_request():
            return _api_error(403, "CSRF_ERROR",
                              "CSRF token missing or invalid.")
        return ("CSRF token missing or invalid, reload the page and try again."), 403

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
    try:
        with _build_availability_service(conn) as service:
            try:
                # List employees that the current user can select for availability management
                selectable_employees = service.get_selectable_employees(current_user)
            except (NotFoundError, ValidationError) as e:
                return f"Error retrieving employees: {str(e)}", 400

            return render_template(
                'avail_select.html',
                employees=selectable_employees,
            )
    except (AttributeError, KeyError, TypeError) as e:
        return f"An error occurred: {str(e)}", 400
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}", 500

@availability_bp.route('/availability/<int:employee_id>', methods=["GET", "POST"])
@login_required
def availability_detail(employee_id):
    """Display and manage availability for a specific employee."""
    conn = get_db_connection()
    try:
        with _build_availability_service(conn) as service:
            try:
                employee = service.employee_service.get_employee(employee_id)
            except NotFoundError:
                return _forbidden()
            
            if employee is None:
                return _forbidden()
            
            if not service.user_can_access_employee(current_user, employee):
                return _forbidden()

            if request.method == "POST":
                if not csrf_is_valid():
                    return _api_error(403, "FORBIDDEN", "CSRF token validation failed")
                try:
                    data = _json_body()
                    if not service.user_can_access_employee(current_user, employee):
                        return _forbidden()
                    updated = service.update_availability(data, employee_id)
                    if not updated:
                        raise NotFoundError("Availability not found")
                    return jsonify({"status": "success", "id": updated, "message": "Availability updated successfully"}), 200
                except ValidationError as error:
                    return _api_error(400, "VALIDATION_ERROR", str(error))
                except NotFoundError as error:
                    return _api_error(404, "NOT_FOUND", str(error))
                except Exception as e:
                    return _api_error(500, "INTERNAL_ERROR", f"An unexpected error occurred: {str(e)}")

            try:
                time_off_objects = service.get_time_off_by_employee(employee_id)
                avail_events, background_events, approved_days = service.availability_db_to_events(
                    service.get_availability_by_employee(employee_id),
                    time_off_objects,
                    employee_id,
                )
            except (NotFoundError, ValidationError) as e:
                return f"Error retrieving availability: {str(e)}", 400
            
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
    except (AttributeError, KeyError, TypeError) as e:
        if request.is_json or request.method == "POST":
            return _api_error(400, "BAD_REQUEST", str(e))
        return f"An error occurred: {str(e)}", 400
    except Exception as e:
        if request.is_json or request.method == "POST":
            return _api_error(500, "INTERNAL_ERROR", f"An unexpected error occurred: {str(e)}")
        return f"An unexpected error occurred: {str(e)}", 500

# ==========================================
# API Routes
# ==========================================

# Gets weekly availabiltiy for an employee
@availability_bp.route('/api/employees/<int:employee_id>/availability', methods=["GET"])
@login_required
def get_employee_availability(employee_id):
    """Get weekly availability for an employee."""
    conn = get_db_connection()
    try:
        with _build_availability_service(conn) as service:
            try:
                employee = service.employee_service.get_employee(employee_id)
            except NotFoundError:
                return _api_error(404, "NOT_FOUND", f"Employee {employee_id} not found")
            
            if employee is None:
                return _api_error(404, "NOT_FOUND", f"Employee {employee_id} not found")

            if not service.user_can_access_employee(current_user, employee):
                return _api_error(403, "FORBIDDEN", "You are not allowed to view this employee's availability")

            try:
                weekly_grid = service.get_weekly_grid(employee_id)
            except (NotFoundError, ValidationError) as e:
                return _api_error(404, "NOT_FOUND", f"No availability found for this employee: {str(e)}")
            
            if not weekly_grid or len(weekly_grid) == 0:
                return _api_error(404, "NOT_FOUND", "No availability found for this employee")

            weekly_list = []
            for avail in weekly_grid:
                if avail is None or type(avail) is not Availability:
                    return _api_error(400, "INVALID_STATE", "Availability object is invalid")
                weekly_list.append(asdict(avail))

            return jsonify({"weekly_grid": weekly_list}), 200
    except (AttributeError, KeyError, TypeError) as e:
        return _api_error(400, "VALIDATION_ERROR", f"Invalid request data: {str(e)}")
    except Exception as e:
        return _api_error(500, "INTERNAL_ERROR", f"An unexpected error occurred: {str(e)}")

# Replace weekly availability grid for an employee
@availability_bp.route('/api/employees/<int:employee_id>/availability', methods=["PUT"])
@login_required
def update_employee_availability(employee_id):
    """
    Replace the entire weekly availability grid for an employee.
    Employees can only update their own. Managers can update employees. Admin can update anyone.
    Request body: {"entries": [{"workday_id": 1, "shift_id": 1, "available": true}, ...]}
    """
    conn = get_db_connection()
    try:
        if not csrf_is_valid():
            return _api_error(403, "FORBIDDEN", "CSRF token validation failed")
        
        with _build_availability_service(conn) as service:
            try:
                employee = service.employee_service.get_employee(employee_id)
            except NotFoundError:
                return _api_error(404, "NOT_FOUND", f"Employee {employee_id} not found")
            
            if employee is None:
                return _api_error(404, "NOT_FOUND", f"Employee {employee_id} not found")

            if not service.user_can_access_employee(current_user, employee):
                return _api_error(403, "FORBIDDEN", "You are not allowed to update this employee's availability")

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

            try:
                availability = service.replace_weekly_grid(employee_id, weekly_grid)
            except NotFoundError as nfe:
                return _api_error(404, "NOT_FOUND", str(nfe))
            except ValidationError as ve:
                return _api_error(400, "VALIDATION_ERROR", str(ve))
            except InvalidStateError as ise:
                return _api_error(400, "INVALID_STATE", str(ise))
            
            avail_list = []
            for avail in availability:
                if avail is None or type(avail) is not Availability:
                    return _api_error(400, "INVALID_STATE", "Availability object is invalid")
                avail_list.append(asdict(avail))

            conn.commit()
            return jsonify({"weekly_grid": avail_list}), 200

    except (AttributeError, KeyError, TypeError) as e:
        conn.rollback()
        return _api_error(400, "VALIDATION_ERROR", f"Invalid request data: {str(e)}")
    except Exception as e:
        conn.rollback()
        return _api_error(500, "INTERNAL_ERROR", f"An unexpected error occurred: {str(e)}")
    
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
        return _api_error(400, "VALIDATION_ERROR", "Invalid shift_id format")

    conn = get_db_connection()
    try:
        with _build_availability_service(conn) as service:
            try:
                workday_id = datetime_obj.isoweekday()

                available_employees = service.get_available_employees_for_shift(workday_id, shift_id)
            except (NotFoundError, ValidationError) as e:
                return _api_error(404, "NOT_FOUND", f"No available employees found: {str(e)}")
            
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
    except (AttributeError, KeyError, TypeError) as e:
        return _api_error(400, "VALIDATION_ERROR", f"Invalid request data: {str(e)}")
    except Exception as e:
        return _api_error(500, "INTERNAL_ERROR", f"An unexpected error occurred: {str(e)}")

@availability_bp.route('/api/time-off-requests', methods=["POST"])
@login_required
def create_time_off_request():
    conn = get_db_connection()
    try:
        with _build_availability_service(conn) as service:
            if not csrf_is_valid():
                return _api_error(403, "FORBIDDEN", "CSRF token validation failed")
            
            try:
                data = _json_body()
            except ValidationError as error:
                return _api_error(400, "VALIDATION_ERROR", str(error))

            try:
                event = service.submit_time_off(data)
                split_events = service.split_background_event(event)
                conn.commit()
                return jsonify({
                    "status": "success",
                    "background_events": split_events,
                }), 201
            except ValidationError as error:
                conn.rollback()
                return _api_error(400, "VALIDATION_ERROR", str(error))
            except ConflictError as error:
                conn.rollback()
                return _api_error(409, "CONFLICT", str(error))
            except InvalidStateError as error:
                conn.rollback()
                return _api_error(409, "INVALID_STATE", str(error))
            except NotFoundError as error:
                conn.rollback()
                return _api_error(404, "NOT_FOUND", str(error))
            except Exception as e:
                conn.rollback()
                return _api_error(500, "INTERNAL_ERROR", f"An unexpected error occurred: {str(e)}")
    except (AttributeError, KeyError, TypeError) as e:
        conn.rollback()
        return _api_error(400, "VALIDATION_ERROR", f"Invalid request data: {str(e)}")
    except Exception as e:
        conn.rollback()
        return _api_error(500, "INTERNAL_ERROR", f"An unexpected error occurred: {str(e)}")
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
            page, page_size = read_paging()
            if current_user.system_role_id == 1:
                try:
                    requests = service.get_time_off_by_employee(current_user.employee_id)
                except ValidationError as error:
                    return _api_error(400, "VALIDATION_ERROR", str(error))
                except NotFoundError as error:
                    return _api_error(404, "NOT_FOUND", str(error))
            else:
                try:
                    requests = service.get_allowed_time_off_requests(current_user)
                except (ValidationError, NotFoundError) as error:
                    return _api_error(400, "VALIDATION_ERROR", str(error))

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
                ],
                "page": page,
                "page_size": page_size,
                "total": len(requests)
            }), 200
    except (AttributeError, KeyError, TypeError) as e:
        return _api_error(400, "VALIDATION_ERROR", f"Invalid request data: {str(e)}")
    except Exception as e:
        return _api_error(500, "INTERNAL_ERROR", f"An unexpected error occurred: {str(e)}")

@availability_bp.route('/api/time-off-requests/<int:request_id>', methods=["PATCH"])
@login_required
@manager_required
def review_time_off_request(request_id):
    conn = get_db_connection()
    try:
        if not csrf_is_valid():
            return _api_error(403, "FORBIDDEN", "CSRF token validation failed")
        
        with _build_availability_service(conn) as service:
            if request_id is None:
                return _api_error(400, "VALIDATION_ERROR", "Request ID is required")
            
            try:
                time_off = service.get_time_off_request(request_id)
            except (NotFoundError, ValidationError) as e:
                return _api_error(400, "VALIDATION_ERROR", f"Error retrieving time-off request: {str(e)}")
            except Exception as e:
                return _api_error(500, "INTERNAL_ERROR", f"An unexpected error occurred: {str(e)}")
            
            if time_off is None:
                return _api_error(404, "NOT_FOUND", "Time-off request not found")
            
            employee_id = time_off.employee_id
            if employee_id is None:
                return _api_error(500, "INTERNAL_ERROR", "Employee ID is required")
            if employee_id == current_user.employee_id:
                return _api_error(403, "FORBIDDEN", "Cannot review your own requests")

            try:
                employee = service.employee_service.get_employee(employee_id)
            except NotFoundError:
                return _api_error(404, "NOT_FOUND", "Employee not found")
            
            if not service.user_can_access_employee(current_user, employee, inclusive=False):
                return _api_error(403, "FORBIDDEN", "You do not have permission to review this request")

            if time_off.status != "Pending":
                return _api_error(409, "CONFLICT", "Time-off request is no longer pending")

            try:
                data = _json_body()
            except ValidationError as error:
                return _api_error(400, "VALIDATION_ERROR", str(error))

            try:
                time_off_obj = service.decide_time_off(request_id, data.get("status"))
                if not time_off_obj:
                    return _api_error(404, "NOT_FOUND", "No pending time-off request found to update")
            except ValidationError as error:
                return _api_error(400, "VALIDATION_ERROR", str(error))
            except NotFoundError as error:
                return _api_error(404, "NOT_FOUND", str(error))
            except ConflictError as error:
                return _api_error(409, "CONFLICT", str(error))
            except InvalidStateError as error:
                return _api_error(400, "INVALID_STATE", str(error))
            except InternalError as error:
                return _api_error(500, "INTERNAL_ERROR", str(error))
            except Exception as e:
                return _api_error(500, "INTERNAL_ERROR", f"An unexpected error occurred: {str(e)}")

            conn.commit()
            
            time_off_objects = service.get_time_off_by_employee(employee_id)
            _, background_events, approved_days = service.availability_db_to_events(
                service.get_availability_by_employee(employee_id),
                time_off_objects,
                employee_id,
            )
            pending_ids = {t.request_id for t in time_off_objects if t.status == "Pending"}
            calendar_background_events = [
                {**segment, "reviewRequestId": bg_event["id"]}
                if bg_event["id"] in pending_ids else segment
                for bg_event in background_events
                for segment in service.split_background_event(bg_event)
            ]
            
            return jsonify({
                "status": "success",
                "updated_time_off": asdict(time_off_obj),
                "background_events": calendar_background_events,
                "approved_days": list(approved_days),
            }), 200
    except (AttributeError, KeyError, TypeError) as e:
        conn.rollback()
        return _api_error(400, "VALIDATION_ERROR", f"Invalid request data: {str(e)}")
    except Exception as e:
        conn.rollback()
        return _api_error(500, "INTERNAL_ERROR", f"An unexpected error occurred: {str(e)}")