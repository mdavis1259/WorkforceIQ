from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for
)

from flask_login import login_required
from database.connection import get_db_connection
from employee_management.EmployeeRepository import EmployeeRepository
from employee_management.EmployeeService import EmployeeService
from scheduling.SchedulingRepository import SchedulingRepository
from scheduling.SchedulingService import SchedulingService


scheduling_bp = Blueprint(
    "scheduling",
    __name__,
    template_folder="templates"
)

def _build_scheduling_service():

    conn = get_db_connection()

    repository = SchedulingRepository(conn)

    service = SchedulingService(repository)

    return service, conn

@scheduling_bp.route("/shift_management")
@login_required
def shift_management():

    service, conn = _build_scheduling_service()
    employee_repository = EmployeeRepository(conn)
    employee_service = EmployeeService(employee_repository)

    try:

        shifts = service.list_shifts()

        requirements = service.list_staffing_requirements()

        workdays = service.list_workdays()

        roles = employee_service.list_roles()

        return render_template(
            "shift_management.html",
            shifts=shifts,
            requirements=requirements,
            workdays=workdays,
            roles=roles
        )

    finally:
        conn.close()

@scheduling_bp.route("/shift_management/workdays", methods=["POST"])
@login_required
def update_workdays():
    
    service, conn = _build_scheduling_service()

    try:

        selected_ids = request.form.getlist("workday_ids")

        all_workdays = service.list_workdays()

        for workday in all_workdays:

            active = (str(workday["workday_id"]) in selected_ids)

            service.update_workday(workday["workday_id"], active)

        return redirect(url_for("scheduling.shift_management")
    )

    finally:
        if conn:
            conn.close()

@scheduling_bp.route("/shift_management/create_shift", methods=["POST"])
@login_required
def create_shift():
    
    service, conn = _build_scheduling_service()

    try:

        service.create_shift(
            request.form["shift_name"],
            request.form["start_time"],
            request.form["end_time"]
        )

        return redirect(url_for("scheduling.shift_management"))

    finally:
        if conn:
            conn.close()
            
@scheduling_bp.route("/shift_management/delete_shift/<int:shift_id>", methods=["POST"])
@login_required
def delete_shift(shift_id):

    service, conn = _build_scheduling_service()

    try:

        service.delete_shift(shift_id)

        return redirect(url_for("scheduling.shift_management"))

    finally:
        if conn:
            conn.close()

@scheduling_bp.route("/shift_management/update_shift/<int:shift_id>", methods=["POST"])
@login_required
def update_shift(shift_id):

    service, conn = _build_scheduling_service()

    try:

        service.update_shift(
            shift_id,
            request.form["shift_name"],
            request.form["start_time"],
            request.form["end_time"]
        )

        return redirect(url_for("scheduling.shift_management"))

    finally:
        if conn:
            conn.close()

@scheduling_bp.route("/shift_management/create_staffing_requirement", methods=["POST"])
@login_required
def create_staffing_requirement():

    service, conn = _build_scheduling_service()

    try:

        selected_workdays = request.form.getlist("workday_ids")

        if not selected_workdays:
            raise ValidationError("At least one workday must be selected.")

        for workday_id in selected_workdays:

            service.create_staffing_requirement(
                workday_id,
                request.form["shift_id"],
                request.form["role_id"],
                request.form["required_count"]
            )

        return redirect(url_for("scheduling.shift_management"))

    finally:
        if conn:
            conn.close()

@scheduling_bp.route("/shift_management/delete_staffing_requirement", methods=["POST"])
@login_required
def delete_staffing_requirement():

    service, conn = _build_scheduling_service()

    try:

        service.delete_staffing_requirement(
            request.form["shift_id"],
            request.form["role_id"]
        )

        return redirect(url_for("scheduling.shift_management"))

    finally:
        if conn:
            conn.close()

@scheduling_bp.route("/shift_management/update_staffing_requirement", methods=["POST"])
@login_required
def update_staffing_requirement():

    service, conn = _build_scheduling_service()

    try:

        service.update_staffing_requirement(
            request.form["shift_id"],
            request.form["role_id"],
            request.form["required_count"]
        )

        return redirect(url_for("scheduling.shift_management"))

    finally:
        if conn:
            conn.close()
