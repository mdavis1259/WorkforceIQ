import uuid
import hmac
import secrets
from datetime import (datetime, timedelta)
from flask import (jsonify, render_template, redirect, request, session, url_for, Blueprint)
from flask_login import (login_required, current_user)
from functools import wraps
from database.connection import get_db_connection
from forecasting.ForecastRepository import ForecastRepository
from forecasting.ForecastService import ForecastService
from dataclasses import asdict
from shared.exceptions import InsufficientHistoryError


forecasting_bp = Blueprint(
    "forecast",
    __name__,
    template_folder="templates"
)

@forecasting_bp.errorhandler(InsufficientHistoryError)
def handle_insufficient_history(error):

    return api_error(
        422,
        "INSUFFICIENT_HISTORY",
        "Not enough data to process the request."
    )

def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)

    return session["csrf_token"]

def csrf_is_valid():
    expected = session.get("csrf_token", "")

    sent = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token", "")
    )

    return(
        bool(expected)
        and hmac.compare_digest(
            sent.encode(),
            expected.encode()
        )
    )

@forecasting_bp.app_context_processor
def add_csrf_token_to_templates():
    return {"csrf_token": csrf_token }

@forecasting_bp.before_request
def check_access():

    if not current_user.is_authenticated:
        return
    if (
        request.method
        in ("POST", "PUT", "PATCH", "DELETE")
        and not csrf_is_valid()
    ):

        return api_error(
            403,
            "CSRF_FAILED",
            "Missing or invalid CSRF token."
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

def api_error(
        status,
        code,
        message,
        details=None
):
    error = {
        "code": code,
        "message": message,
        "request_id": uuid.uuid4().hex[:8]
    }

    if details is not None:
        error["details"] = details

    return jsonify({
        "error": error
    }), status

def _build_forecast_service():
    conn = get_db_connection()
    repository = ForecastRepository(conn)
    service = ForecastService(repository)

    return service, conn

@forecasting_bp.route("/forecast", methods=["GET", "POST"])
@login_required
@manager_required
def forecast():

    if request.method == "POST":
        week_start = request.form["week_start"]

        return redirect(url_for("forecast.forecast", week_start=week_start))

    conn = None

    try:
        service, conn = _build_forecast_service()

        selected_week_start = request.args.get("week_start")

        # First visit to page
        if not selected_week_start:
            forecasts = []

            return render_template("forecast.html", forecasts=forecasts, selected_week_start="")

        # Retrieve selected forecast period
        start_date = datetime.strptime(selected_week_start, "%Y-%m-%d")

        end_date = (start_date + timedelta(days=13)).strftime("%Y-%m-%d")

        forecasts = service.get_range(selected_week_start, end_date)

        # If no forecasts exist yet, generate them
        if not forecasts:
            forecasts = service.generate_forecast(selected_week_start)

        return render_template("forecast.html", forecasts=forecasts, selected_week_start=selected_week_start)

    finally:
        if conn:
            conn.close()

@forecasting_bp.route(
    "/forecast/update",
    methods=["POST"]
)
@login_required
@manager_required
def update_forecast():

    conn = None

    try:
        service, conn = _build_forecast_service()

        forecast_id = int(
            request.form["forecast_id"]
        )

        projected_sales = float(
            request.form["projected_sales"]
        )

        service.update_forecast(
            forecast_id,
            projected_sales
        )
    
    finally:
        conn.close()

    return redirect(
        url_for("forecast.forecast", week_start=request.form["week_start"])
    )

@forecasting_bp.route(
    "/forecast/recalculate",
    methods=["POST"]
)
@login_required
@manager_required
def recalculate_forecast():

    print(request.form)

    labor_target_percent = float(request.form["labor_target_percent"])

    uncertainty = float(request.form["uncertainty"])

    conn = None

    try:
        service, conn = _build_forecast_service()

        service.update_draft_forecasts(labor_target_percent=labor_target_percent, uncertainty=uncertainty)

        service.generate_draft_forecast(labor_target_percent=labor_target_percent, uncertainty=uncertainty)

    finally:
        if conn:
            conn.close()

    return redirect(url_for("forecast.forecast", week_start=request.form["week_start"]))

@forecasting_bp.route(
    "/forecast/approve",
    methods=["POST"]
)
@login_required
@manager_required
def approve_forecast():

    conn = None

    try:
        service, conn = _build_forecast_service()

        forecast_id = request.form.get("forecast_id")
        
        print("Forecast ID: " + forecast_id)

        if not forecast_id or forecast_id == "None":
            
            raise ValueError("Forecast ID missing from approve request")

        forecast_id = int(forecast_id)

        service.approve_forecast(forecast_id)
    finally:
        if conn:
            conn.close()

    return redirect(url_for("forecast.forecast", week_start=request.form["week_start"]))

@forecasting_bp.route(
    "/api/forecasts/submit", methods=["POST"]
)
@login_required
@manager_required
def submit_historical_data():
    """ Allows the user to upload historical data in CSV format (Future Release Feature)"""
    pass

@forecasting_bp.route(
    "/api/forecasts/generate", methods=["POST"]
)
@login_required
@manager_required
def generate_forecast_api():
    conn = None

    try:
        service, conn = _build_forecast_service()

        forecasts = service.generate(request.get_json())

        return jsonify([
            asdict(forecast)
            for forecast in forecasts
        ]), 201

    finally:
        if conn:
            conn.close()

@forecasting_bp.route(
    "/api/forecasts", methods=["GET"]
)
@login_required
@manager_required
def get_forecasts():

    conn = None

    try:
        service, conn = _build_forecast_service()

        start_date = request.args.get("from")
        end_date = request.args.get("to")

        forecasts = service.get_range(start_date, end_date)

        return jsonify([
            asdict(forecast)
            for forecast in forecasts
        ]), 200

    finally:
        if conn:
            conn.close()
