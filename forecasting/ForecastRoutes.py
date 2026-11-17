from flask import (render_template, request, Blueprint)
from flask_login import login_required
from database.connection import get_db_connection
from forecasting.ForecastRepository import ForecastRepository
from forecasting.ForecastService import ForecastService


forecasting_bp = Blueprint(
    "forecast",
    __name__,
    template_folder="templates"
)

@forecasting_bp.route("/forecast", methods=["GET", "POST"])
@login_required
def forecast():

    conn = None

    try:
        conn = get_db_connection()

        repository = ForecastRepository(conn)

        service = ForecastService(repository)

        forecasts = []

        if request.method == "POST":
            
            week_start = request.form["week_start"]

            forecasts = service.generate_two_week_forecast(week_start)

        else:

            forecasts = service.generate_two_week_forecast()

    finally:
        if conn:
            conn.close()

    return render_template("forecast.html", forecasts=forecasts)