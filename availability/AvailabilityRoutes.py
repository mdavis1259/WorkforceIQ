from availability.AvailabilityRepository import (
    create_availability,
    delete_availability,
    get_employee_availability,
    update_availability,
)
from availability.AvailabilityService import availabilityDBtoEvents
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user

availability_bp = Blueprint('availability', __name__, template_folder='templates')

@availability_bp.route('/availability', methods=["GET", "POST", "DELETE"])
def availability():
    if request.method == "POST":
        data = request.get_json()
        try:
            if not isinstance(data, dict) or data.get("id") is None:
                availability_id = create_availability(current_user.employee_id, data)
                if availability_id is None:
                    return jsonify({"status": "error",
                                    "message": "Employee not found"
                                    }), 404
                return jsonify({
                    "status": "success",
                    "id": availability_id,
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

    avail_events = availabilityDBtoEvents(get_employee_availability(current_user.employee_id))
    return render_template('availability.html', availability=avail_events)