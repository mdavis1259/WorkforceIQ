from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for
)

from flask_login import login_required
from database.connection import get_db_connection
from employee_management.EmployeeService import EmployeeService
from employee_management.EmployeeRepository import EmployeeRepository
from scheduling.SchedulingRepository import SchedulingRepository
from scheduling.SchedulingService import SchedulingService
from availability.AvaliabilityRepository import AvaliabilityRepository
from availability.AvailabilityService import AvailabilityService
from forecasting.ForecastRepository import ForecastRepository
from forecasting.ForecastService import ForecastService
from availability.AvailabilityRepository import AvailabilityRepository
from availability.AvailabilityService import AvailabilityService


scheduling_bp = Blueprint(
    "scheduling",
    __name__,
    template_folder="templates"
)

def _build_scheduling_service():

    # Establish database connection
    conn = get_db_connection()

    # Instantiate repositories for service instantiation
    scheduling_repository = SchedulingRepository(conn)
    employee_repository = EmployeeRepository(conn)
    availability_repository = AvailabliityRepostiory(conn)
    forecasting_repository = ForecastRepository(conn)


    employee_service = EmployeeService(employee_repository)
    availability_service = AvailabilityService(availability_repository)
    forecasting_service = ForecastService(forecasting_repository)
    availability_repository = AvailabilityRepository(conn)
    availability_service = AvailabilityService(availability_repository, employee_service)

    service = SchedulingService(
        scheduling_repository,
        employee_service,
        forecasting_service,
        availability_service
    ) 

    return service, conn

@scheduling_bp.route("/shift_management")
@login_required
def shift_management():

    service, conn = _build_scheduling_service()

    try:

        shifts = service.list_shifts()

        requirements = service.list_staffing_requirements()

        workdays = service.list_workdays()

        roles = service.employee_service.list_roles()

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
            request.form["requirement_id"],
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
            request.form["requirement_id"],
            request.form["required_count"]
        )

        return redirect(url_for("scheduling.shift_management"))

    finally:
        if conn:
            conn.close()

@scheduling_bp.route("/schedule/generate", methods=["POST"])
@login_required
def generate_schedule():

    service, conn = _build_scheduling_service()

    try:

        week_start = request.form["week_start"]

        schedule, summary = service.generate_week(week_start)

        assignments = service.get_assignments(schedule["schedule_id"])

        return render_template(
            "schedule.html", 
            schedule=schedule, 
            assignments=assignments,
            summary=summary
        )
    
    finally:
        if conn:
            conn.close()

@scheduling_bp.route("/schedule")
@login_required
def schedule():

    service, conn = _build_scheduling_service()

    try:

        schedule = None
        assignments = []

        summary = {
            "requirements_processed": 0,
            "employees_considered": 0,
            "employees_assigned": 0,
            "unfilled_requirements": 0,
            "requirements": []
        }

        week_start = request.args.get("week_start")

        if week_start:

            schedule = service.get_schedule(week_start)

            if schedule:

                assignments = service.get_assignments(schedule["schedule_id"])
        return render_template("schedule_ui.html", schedule=schedule, assignments=assignments)
    
    finally:
        if conn:
            conn.close()
