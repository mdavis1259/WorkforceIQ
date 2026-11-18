import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import date, datetime, timedelta


class ForecastService:

    def __init__(self, repository):
        self.repository = repository

    def generate_two_week_forecast(self, start_date=None, labor_percent=18.0, uncertainty=1.0):
        """
        Generate a 14-day staffing forecast
        using historical demand data.
        """

        if start_date:
            base_date = datetime.fromisoformat(start_date).date()
        
        else:

            base_date = date.today()

        if hasattr(self.repository, "get_forecast_by_date"):
            existing_forecast = self.repository.get_forecast_by_date(base_date.isoformat())

            if existing_forecast:
                return self.repository.get_forecasts_from_date(base_date.isoformat())

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
                timedelta(days=len(forecasts))
            ).isoformat()
            
            prediction = float(
                model.predict([[forecast_day]])[0]
            )

            labor_budget = round(
                prediction * (labor_percent / 100),
                2
            )

            self.repository.save_forecast(
                forecast_date,
                round(prediction, 2),
                round(
                    prediction - (standard_deviation * uncertainty),
                    2
                ),
                round(
                    prediction + (standard_deviation * uncertainty),
                    2
                ),
                None,
                labor_budget,
                "Draft"
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
                "status": "Draft"
            })

        if hasattr(self.repository, "get_forecasts_from_date"):
            return self.repository.get_forecasts_from_date(base_date.isoformat())
        
        return forecasts

    def generate_draft_forecast(self, labor_percent=18.0, uncertainty=1.0):
        return self.generate_two_week_forecast()
    
    def get_forecasts(self):
        return self.repository.get_forecasts()

    def update_forecast(self, forecast_id, projected_sales, labor_percent=18.0):

        labor_budget = round(projected_sales * (labor_percent / 100), 2)

        self.repository.update_forecast(forecast_id, projected_sales, labor_budget)

    def approve_forecast(self, forecast_id):

        self.repository.approve_forecast(forecast_id)

    def update_draft_forecasts(self, labor_percent, uncertainty):

        self.repository.update_draft_forecasts(labor_percent, uncertainty)
