from assistant.AssistantTests import service
from flask import (
    Blueprint,
    render_template,
    jsonify,
    redirect,
    request,
    session,
    url_for
)

from flask_login import current_user, login_required
from database.connection import get_db_connection
from availability.AvailabilityRepository import AvailabilityRepository
from availability.AvailabilityService import AvailabilityService
from employee_management.EmployeeRepository import EmployeeRepository
from employee_management.EmployeeService import EmployeeService

availability_bp = Blueprint(
    'availability',
    __name__,
    template_folder='templates'
)

def _build_availability_service(conn):
    employee_repo = EmployeeRepository(conn)
    employee_service = EmployeeService(employee_repo)

    #Get repository and service
    availability_repo = AvailabilityRepository(conn)
    service = AvailabilityService(availability_repo, employee_service)
    return service


def _selected_employee_id(service):
    if current_user.system_role_id == 1:
        session["availability_employee"] = current_user.employee_id
        return current_user.employee_id

    employee_id = session.get("availability_employee", current_user.employee_id)
    if current_user.system_role_id == 2:
        selectable_employee_ids = {
            employee.employee_id
            for employee in service.list_employees(associates_only=True)
        }
        if employee_id != current_user.employee_id and employee_id not in selectable_employee_ids:
            session.pop("availability_employee", None)
            return None
    return employee_id


@availability_bp.route('/availability', methods=["GET", "POST"])
@login_required
def availability():
    conn = get_db_connection()
    try:
        service = _build_availability_service(conn)

        employee_id = _selected_employee_id(service)
        if employee_id is None:
            return redirect(url_for("availability.avail_select"))


        # Used for Availability updates
        if request.method == "POST":
            data = request.get_json()
            print("In POST with data:", data)
            try:
                updated = service.update_availability(data, employee_id)
            except ValueError as error:
                return jsonify({"status": "error", "message": str(error)}), 400
            if not updated:
                return jsonify({"status": "error", "message": "Availability not found"}), 404
            return jsonify({"status": "success", "id": updated, "message": "Availability updated successfully"}), 200
        

        time_off_requests = service.get_time_off_by_employee(employee_id)
        avail_events, background_events, approved_days = service.availability_db_to_events(
            service.get_availability_by_employee(employee_id),
            time_off_requests,
            employee_id,
        )
        can_review = current_user.system_role_id in (2, 3) and employee_id != current_user.employee_id
        pending_ids = {row["request_id"] for row in time_off_requests if row["status"] == "Pending"}
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
                                       "start": row["start_date"][:10],
                                       "end": row["end_date"][:10],
                                   }
                                   for row in time_off_requests
                                   if row["status"] != "Cancelled"
                               ],
                               employee=service.employee_service.get_employee(employee_id))
    finally:
        conn.close()


@availability_bp.route('/api/time-off-requests', methods=["POST"])
@login_required
def create_time_off_request():
    conn = get_db_connection()
    try:
        service = _build_availability_service(conn)
        employee_id = _selected_employee_id(service)
        if employee_id is None:
            return jsonify({"status": "error", "message": "Employee is not accessible"}), 403
        try:
            event = service.create_time_off_request(request.get_json(silent=True), employee_id)
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400
        return jsonify({
            "status": "success",
            "event": event,
            "background_events": service.split_background_event(event),
        }), 201
    finally:
        conn.close()


@availability_bp.route('/api/time-off-requests/<int:request_id>', methods=["GET", "PUT"])
@login_required
def review_time_off_request(request_id):
    if current_user.system_role_id not in (2, 3):
        return jsonify({"status": "error", "message": "Not authorized to review requests"}), 403
    conn = get_db_connection()
    try:
        service = _build_availability_service(conn)
        employee_id = _selected_employee_id(service)
        if employee_id is None or employee_id == current_user.employee_id:
            return jsonify({"status": "error", "message": "Employee is not accessible for review"}), 403
        review = service.get_time_off_review(request_id, employee_id)
        if review is None:
            return jsonify({"status": "error", "message": "Time-off request not found"}), 404
        if review["status"] != "Pending":
            return jsonify({"status": "error", "message": "Time-off request is no longer pending"}), 409
        if request.method == "GET":
            return jsonify({"status": "success", "request": review})
        try:
            updated = service.review_time_off_request(request_id, employee_id, request.get_json(silent=True))
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400
        if not updated:
            return jsonify({"status": "error", "message": "Time-off request is no longer pending"}), 409
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


@availability_bp.route('/avail_select', methods=["GET", "POST"])
@login_required
def avail_select():
    conn = get_db_connection()
    try:
        service = _build_availability_service(conn)

        if current_user.system_role_id == 1:
            session["availability_employee"] = current_user.employee_id
            return redirect(url_for("availability.availability"))

        selectable_employees = service.list_employees(
            associates_only=current_user.system_role_id == 2
        )

        if request.method == "POST":
            try:
                availability_employee = int(request.form["employee_id"])
            except (TypeError, ValueError):
                return "Please select a valid employee.", 400

            allowed_employee_ids = {
                employee.employee_id for employee in selectable_employees
            }
            if current_user.system_role_id in (2, 3):
                allowed_employee_ids.add(current_user.employee_id)
            if availability_employee not in allowed_employee_ids:
                return "Please select a valid employee.", 400

            session["availability_employee"] = availability_employee
            return redirect(url_for("availability.availability"))

        return render_template(
            'avail_select.html',
            employees=selectable_employees,
        )
    finally:
        conn.close()