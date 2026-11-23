import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import date, datetime, timedelta
from forecasting.Forecast import Forecast
from errors import InsufficientHistoryError


class ForecastService:

    def __init__(self, repository):
        self.repository = repository

    def generate(self, data):
        return self.generate_forecast(
            start_date=data.get("start_date"),
            horizon_days=data.get("horizon_days", 14),
            sales_per_labor_hour_goal=data.get("sales_per_labor_hour_goal", 55.0),
            labor_target_percent=data.get("labor_target_percent", 18.0),
            uncertainty=data.get("uncertainty", 1.0)
        )

    def generate_forecast(self, start_date=None, horizon_days=14, sales_per_labor_hour_goal=55.0, labor_target_percent=18.0, uncertainty=1.0):
        """
        Generate a staffing forecast
        using historical demand data.
        """
        if horizon_days < 1 or horizon_days > 28:
            raise ValueError("horizon_days must be between 1 and 28.")

        if sales_per_labor_hour_goal <= 0:
            raise ValueError("sales_per_labor_hour_goal must be greater than 0.")

        if start_date:
            base_date = datetime.fromisoformat(start_date).date()
        
        else:

            base_date = date.today()
           
        end_date = (base_date + timedelta(days=horizon_days - 1)).isoformat()            
        
        
        history = self.repository.get_demand_history()

        if len(history) < 56:
            raise InsufficientHistoryError(
                "At least 8 weeks of demand history is required."
            )

        sales = [row["sales_amount"] for row in history]

        days = np.arange(1, len(sales) + 1).reshape(-1, 1)

        model = LinearRegression()
        model.fit(days, sales)

        standard_deviation = np.std(sales)

        forecasts = []

        for offset in range(horizon_days):
            forecast_date = (
                base_date +
                timedelta(days=offset)
            ).isoformat()

            existing = self.repository.get_forecast_by_date(forecast_date)

            if existing:
                forecasts.append(existing)
                continue

            forecast_day = len(sales) + offset + 1
            
            prediction = float(
                model.predict([[forecast_day]])[0]
            )

            labor_budget = round(
                prediction * (labor_target_percent / 100),
                2
            )

            required_labor_hours = self.calculate_required_labor_hours(prediction, sales_per_labor_hour_goal)

            print(
                f"Saving forecast: "
                f"{forecast_date} "
                f"sales={round(prediction, 2)} "
                f"hours={required_labor_hours} "
                f"budget={labor_budget}"
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
                required_labor_hours,
                labor_budget,
                "Draft"
            )

            forecasts.append(
                Forecast(
                    forecast_date=forecast_date,
                    projected_sales=round(prediction, 2),
                    projected_sales_low=round(prediction - (standard_deviation * uncertainty), 2),
                    projected_sales_high=round(prediction + (standard_deviation * uncertainty), 2),
                    required_labor_hours=required_labor_hours,
                    labor_budget=labor_budget,
                    status="Draft"
                )
            )

        return forecasts

    def generate_draft_forecast(self, labor_target_percent=18.0, uncertainty=1.0):
        return self.generate({ "labor_target_percent": labor_target_percent, "uncertainty": uncertainty })
    
    def get_forecasts(self):
        return self.repository.get_forecasts()

    def get_range(self, start_date, end_date):
        return self.repository.get_range(start_date, end_date)

    def update_forecast(self, forecast_id, projected_sales, labor_target_percent=18.0):

        labor_budget = round(projected_sales * (labor_target_percent / 100), 2)

        self.repository.update_forecast(forecast_id, projected_sales, labor_budget)

    def approve_forecast(self, forecast_id):

        self.repository.approve_forecast(forecast_id)

    def update_draft_forecasts(self, labor_target_percent, uncertainty):

        self.repository.update_draft_forecasts(labor_target_percent, uncertainty)

    def calculate_required_labor_hours(self, projected_sales, sales_per_labor_hour_goal):
        if sales_per_labor_hour_goal <= 0:
            raise ValueError("sales_per_labor_hour_goal must be greater than 0.")
        
        return round(projected_sales / sales_per_labor_hour_goal, 2)

    def get_model_quality(self):
        pass