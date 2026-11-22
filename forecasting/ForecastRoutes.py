from flask import (jsonify, render_template, redirect, request, url_for, Blueprint)
from flask_login import login_required
from database.connection import get_db_connection
from forecasting.ForecastRepository import ForecastRepository
from forecasting.ForecastService import ForecastService
from dataclasses import asdict

forecasting_bp = Blueprint(
    "forecast",
    __name__,
    template_folder="templates"
)

def _build_forecast_service():
    conn = get_db_connection()
    repository = ForecastRepository(conn)
    service = ForecastService(repository)

    return service, conn

@forecasting_bp.route("/forecast", methods=["GET", "POST"])
@login_required
def forecast():

    conn = None

    try:
        service, conn = _build_forecast_service()

        forecasts = []

        if request.method == "POST":
            
            week_start = request.form["week_start"]

            forecasts = service.generate_forecast(week_start)

        else:

            forecasts = service.generate_forecast()

    finally:
        if conn:
            conn.close()

    return render_template("forecast.html", forecasts=forecasts)

@forecasting_bp.route(
    "/forecast/update",
    methods=["POST"]
)
@login_required
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
        url_for("forecast.forecast")
    )

@forecasting_bp.route(
    "/forecast/recalculate",
    methods=["POST"]
)
@login_required
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

    return redirect(url_for("forecast.forecast"))

@forecasting_bp.route(
    "/forecast/approve",
    methods=["POST"]
)
@login_required
def approve_forecast():

    conn = None

    try:
        service, conn = _build_forecast_service()
        
        forecast_id = int(request.form["forecast_id"])

        service.approve_forecast(forecast_id)
    finally:
        if conn:
            conn.close()

    return redirect(url_for("forecast.forecast"))

@forecasting_bp.route(
    "/api/forecasts/submit", methods=["POST"]
)
@login_required
def submit_historical_data():
    pass

@forecasting_bp.route(
    "/api/forecasts/generate", methods=["POST"]
)
@login_required
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
