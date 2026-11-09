from flask import (render_template, Blueprint)
from flask_login import login_required
from forecasting.ForecastService import ForecastService

forecasting_bp = Blueprint(
    "forecast",
    __name__,
    template_folder="templates"
)

@forecasting_bp.route("/forecast")
@login_required
def forecast():

    predicted_demand = ForecastService.generate_forecast()

    recommended_staff = round(predicted_demand / 30)

    return render_template("forecast.html", demand=predicted_demand, staff=recommended_staff)