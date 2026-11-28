from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
    redirect,
    url_for
)
from dataclasses import asdict
from datetime import datetime, timedelta
from flask_login import login_required
from functools import wraps
from database.connection import get_db_connection
from employee_management.EmployeeService import EmployeeService
from employee_management.EmployeeRepository import EmployeeRepository
from scheduling.SchedulingRepository import SchedulingRepository
from scheduling.SchedulingService import SchedulingService
from availability.AvailabilityService import AvailabilityService
from forecasting.ForecastRepository import ForecastRepository
from forecasting.ForecastService import ForecastService
from availability.AvailabilityRepository import AvailabilityRepository
from availability.AvailabilityService import AvailabilityService
from shared.exceptions import ValidationError


scheduling_bp = Blueprint(
    "scheduling",
    __name__,
    template_folder="templates"
)

def manager_required(view):

    @wraps(view)
    def wrapper(*args, **kwargs):

        if current_user.system_role_id < 2:
            return jsonify({
                "error": {
                    "code": "FORBIDDEN",
                    "message": "You do not have permission to do that."
                }
            }), 403

        return view(*args, **kwargs)

    return wrapper

def _build_scheduling_service():

    # Establish database connection
    conn = get_db_connection()

    # Instantiate repositories for service instantiation
    scheduling_repository = SchedulingRepository(conn)
    employee_repository = EmployeeRepository(conn)
    availability_repository = AvailabilityRepository(conn)
    forecasting_repository = ForecastRepository(conn)


    employee_service = EmployeeService(employee_repository)
    forecasting_service = ForecastService(forecasting_repository)
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
@manager_required
def shift_management():

    service, conn = _build_scheduling_service()

    try:

        data = service.get_shift_management_data()

        return render_template(
            "shift_management.html",
            shifts=data["shifts"],
            requirements=data["requirements"],
            workdays=data["workdays"],
            roles=data["roles"]
        )

    finally:
        conn.close()

@scheduling_bp.route("/shift_management/workdays", methods=["POST"])
@login_required
@manager_required
def update_workdays():
    
    service, conn = _build_scheduling_service()

    try:

        selected_ids = request.form.getlist("workday_ids")

        all_workdays = service.update_workdays(selected_ids)

        for workday in all_workdays:

            active = (str(workday["workday_id"]) in selected_ids)

            service.availability_service.update_workday(workday["workday_id"], active)

        return redirect(
            url_for("scheduling.shift_management")
        )

    finally:
        if conn:
            conn.close()

@scheduling_bp.route("/shift_management/create_shift", methods=["POST"])
@login_required
@manager_required
def create_shift():
    
    service, conn = _build_scheduling_service()

    try:

        service.availability_service.create_shift(
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
@manager_required
def delete_shift(shift_id):

    service, conn = _build_scheduling_service()

    try:

        service.availability_service.delete_shift(shift_id)

        return redirect(url_for("scheduling.shift_management"))

    finally:
        if conn:
            conn.close()

@scheduling_bp.route("/shift_management/update_shift/<int:shift_id>", methods=["POST"])
@login_required
@manager_required
def update_shift(shift_id):

    service, conn = _build_scheduling_service()

    try:

        service.availability_service.update_shift(
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
@manager_required
def create_staffing_requirement():

    service, conn = _build_scheduling_service()

    try:

        selected_workdays = request.form.getlist("workday_ids")

        if not selected_workdays:
            raise ValidationError([
                {
                    "field": "workday_ids",
                    "issue": "At least one workday must be selected"
                }
            ])

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
@manager_required
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
@manager_required
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

        assignments = service.get_assignments(schedule.schedule_id)

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
def schedule_workbench():

    service, conn = _build_scheduling_service()

    try:

        week_start = request.args.get("week_start")

        schedule = None
        assignments = []

        forecast_status = "missing"
        
        forecast_summary = {
                "projected_sales": 0,
                "required_labor_hours": 0,
                "labor_budget": 0
        }

        week_forecasts = []

        if week_start:

            # Forecast
            week_start_date = datetime.strptime(week_start, "%Y-%m-%d").date()

            end_date = (week_start_date + timedelta(days=6)).isoformat()

            week_forecasts = service.forecasting_service.get_range(week_start, end_date)

            if week_forecasts and all(f.status == "Approved" for f in week_forecasts):
                forecast_status = "approved"
            
            elif any(f.status == "Approved" for f in week_forecasts):
                forecast_status = "partial"
            
            else:
                forecast_status = "draft"
                

            forecast_summary = {
                "projected_sales": sum(f.projected_sales for f in week_forecasts),
                "required_labor_hours": sum(f.required_labor_hours for f in week_forecasts),
                "labor_budget": sum(f.labor_budget for f in week_forecasts)
            }

            # Schedule
            schedule = service.get_week(week_start)

            if schedule:
                assignments = service.get_assignments(schedule.schedule_id)

        return render_template(
            "schedule_ui.html", 
            week_start=week_start,
            schedule=schedule, 
            assignments=assignments,
            forecast_status=forecast_status,
            forecast_summary=forecast_summary,
            forecasts=week_forecasts,
            today=datetime.today().strftime("%Y-%m-%d")    
        )
    
    finally:
        if conn:
            conn.close()

@scheduling_bp.route("/api/schedules")
@login_required
def get_schedule_api():

    service, conn = _build_scheduling_service()

    try:
        week_start = request.args.get("week_start")

        if not week_start:
            raise ValidationError([
                {
                    "field": "week_start",
                    "issue": "required"
                }
            ])

        schedule = service.get_week(week_start)

        return jsonify(asdict(schedule))
    finally:
        conn.close()

@scheduling_bp.route("/api/schedules/cost")
@login_required
def schedule_cost():

    service, conn = _build_scheduling_service()

    try:
        week_start = request.args.get("week_start")

        result = service.compute_cost(week_start)

        return jsonify(result)
    finally:
        conn.close()

@scheduling_bp.route(
    "/api/schedules/shifts/<int:shift_id>",
    methods=["GET"]
)
@login_required
def get_shift_details(shift_id):

    service, conn = _build_scheduling_service()

    try:

        schedule_id = int(request.args["schedule_id"])

        workday_id = int(request.args["workday_id"])

        schedule_date = request.args["schedule_date"]

        details = service.get_shift_details(schedule_id, shift_id, schedule_date, workday_id)

        return jsonify({
            "required_count": details["required_count"],
            "assigned_count": details["assigned_count"],
            "open_slots": details["open_slots"],
            "requirements": [asdict(r) for r in details["requirements"]],
            "assignments": [asdict(a) for a in details["assignments"]]
        })

    finally:
        conn.close()

@scheduling_bp.route(
    "/api/schedules/assignments",
    methods=["POST"]
)
@login_required
@manager_required
def add_assignment():

    service, conn = _build_scheduling_service()

    try:
        assignment = service.add_assignment(request.json)

        return jsonify(asdict(assignment)), 201
    
    finally:
        conn.close()

@scheduling_bp.route(
    "/api/schedules/assignments/<int:assignment_id>",
    methods=["PUT"]
)
@login_required
@manager_required
def update_assignment(assignment_id):

    service, conn = _build_scheduling_service()

    try:
        assignment = service.update_assignment(assignment_id, request.json)

        return jsonify(asdict(assignment))
    
    finally:
        conn.close()

@scheduling_bp.route(
    "/api/schedules/assignments/<int:assignment_id>",
    methods=["DELETE"]
)
@login_required
@manager_required
def remove_assignment(assignment_id):

    service, conn = _build_scheduling_service()

    try:
        service.remove_assignment(assignment_id)

        return "", 204
    
    finally:
        conn.close()


@scheduling_bp.route(
    "/api/schedules/approve",
    methods=["POST"]
)
@login_required
@manager_required
def approve_schedule():

    service, conn = _build_scheduling_service()

    try:

        result = service.approve_week(request.json)

        return jsonify(result)
    
    finally:
        conn.close()

@scheduling_bp.route(
    "/api/schedules/generate",
    methods=["POST"]
)
@login_required
@manager_required
def generate_schedule_api():

    service, conn = _build_scheduling_service()

    try:

        result = service.generate_week(request.json)

        return jsonify(result), 201

    finally:
        conn.close()
    

