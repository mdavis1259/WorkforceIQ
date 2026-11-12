from availability.AvailabilityRepository import (
    create_availability_series,
    delete_availability,
    get_employee_availability,
    update_availability,
)
from availability.AvailabilityService import (
    availability_db_to_events,
    list_employees,
    build_availability_occurrences
)
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

availability_bp = Blueprint('availability', __name__, template_folder='templates')


@availability_bp.route('/availability', methods=["GET", "POST", "DELETE"])
@login_required
def availability():
    if current_user.system_role_id == 1:
        employee_id = current_user.employee_id
        session["availability_employee"] = employee_id
    else:
        employee_id = session.get("availability_employee", current_user.employee_id)
        if current_user.system_role_id == 2:
            selectable_employee_ids = {
                employee.employee_id
                for employee in list_employees(associates_only=True)
            }
            if (
                employee_id != current_user.employee_id
                and employee_id not in selectable_employee_ids
            ):
                session.pop("availability_employee", None)
                return redirect(url_for("availability.avail_select"))

    if request.method == "POST":
        data = request.get_json()
        try:
            if not isinstance(data, dict) or data.get("id") is None:
                occurrences = build_availability_occurrences(data)
                created_events = create_availability_series(employee_id, occurrences)
                if created_events is None:
                    return jsonify({"status": "error",
                                    "message": "Employee not found"
                                    }), 404
                return jsonify({
                    "status": "success",
                    "id": created_events[0]["id"],
                    "events": created_events,
                    "message": "Availability created successfully",
                }), 201
            updated = update_availability(data)
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400
        if not updated:
            return jsonify({"status": "error", "message": "Availability not found"}), 404
        return jsonify({"status": "success", "message": "Availability updated successfully"}), 200

    if request.method == "DELETE":
        data = request.get_json()
        try:
            deleted = delete_availability(data)
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400
        if not deleted:
            return jsonify({"status": "error", "message": "Availability not found"}), 404
        return jsonify({"status": "success", "message": "Availability deleted successfully"}), 200

    avail_events = availability_db_to_events(get_employee_availability(employee_id))
    return render_template('availability.html', availability=avail_events)


@availability_bp.route('/avail_select', methods=["GET", "POST"])
@login_required
def avail_select():
    if current_user.system_role_id == 1:
        session["availability_employee"] = current_user.employee_id
        return redirect(url_for("availability.availability"))

    selectable_employees = list_employees(
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