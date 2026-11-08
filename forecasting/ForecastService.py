import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import date, timedelta


class ForecastService:

    def __init__(self, repository):
        self.repository = repository

    def generate_two_week_forecast(self):
        """
        Generate a 14-day staffing forecast
        using historical demand data.
        """

        base_date = date.today()

        history = self.repository.get_demand_history()

        if len(history) < 7:
            return []

        sales = [row["sales_amount"] for row in history]

        days = np.arange(1, len(sales) + 1).reshape(-1, 1)

        model = LinearRegression()
        model.fit(days, sales)

        standard_deviation = np.std(sales)

        forecasts = []

        for forecast_day in range(
            len(sales) + 1,
            len(sales) + 15
        ):
            forecast_date = (
                base_date +
                timedelta(days=len(forecasts) + 1)
            ).isoformat()
            
            prediction = float(
                model.predict([[forecast_day]])[0]
            )

            forecasts.append({
                "forecast_date": forecast_date,
                "projected_sales": round(prediction, 2),
                "projected_sales_low": round(
                    prediction - standard_deviation,
                    2
                ),
                "projected_sales_high": round(
                    prediction + standard_deviation,
                    2
                ),
            })

        return forecasts
    