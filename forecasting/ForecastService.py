import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import date, datetime, timedelta


class ForecastService:

    def __init__(self, repository):
        self.repository = repository

    def generate_two_week_forecast(self, start_date):
        """
        Generate a 14-day staffing forecast
        using historical demand data.
        """

        base_date = datetime.fromisoformat(start_date).date()

        history = self.repository.get_demand_history()

        # Replace existing forecast projections
        # with the newest forecast generation.
        self.repository.clear_forecasts()

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
                timedelta(days=len(forecasts))
            ).isoformat()
            
            prediction = float(
                model.predict([[forecast_day]])[0]
            )

            labor_percent = 18.0

            labor_budget = round(
                prediction * (labor_percent / 100),
                2
            )

            self.repository.save_forecast(
                forecast_date,
                round(prediction, 2),
                round(
                    prediction - standard_deviation,
                    2
                ),
                round(
                    prediction + standard_deviation,
                    2
                ),
                None,
                labor_budget
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
                "labor_budget": labor_budget,
                "status": "Pending Review"
            })

        return forecasts
    
    def get_forecasts(self):
        return self.repository.get_forecasts()