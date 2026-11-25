from forecasting.Forecast import Forecast
from datetime import (datetime, timedelta)

class ForecastRepository:
    def __init__(self, conn):
        self.conn = conn

    def row_to_forecast(self, row):
        return Forecast(
            forecast_id=row["forecast_id"],
            forecast_date=row["forecast_date"],
            projected_sales=row["projected_sales"],
            projected_sales_low=row["projected_sales_low"],
            projected_sales_high=row["projected_sales_high"],
            required_labor_hours=row["required_labor_hours"],
            labor_budget=row["labor_budget"],
            status=row["status"]
        )

    def get_demand_history(self):
        """
        Retrieve historical demand records
        ordered by date.
        """

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT demand_date,
                   sales_amount
            FROM DemandHistory
            ORDER BY demand_date
        """)

        return cursor.fetchall()

    def clear_forecasts(self):
        """
        Remove previously generated forecasts.
        """

        cursor = self.conn.cursor()

        cursor.execute("""
            DELETE FROM Forecasts
        """)

        self.conn.commit()

    def save_forecast(
        self,
        forecast_date,
        projected_sales,
        projected_sales_low,
        projected_sales_high,
        required_labor_hours,
        labor_budget,
        status="Draft"
    ):
        """
        Persist a forecast record.
        """

        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO Forecasts
            (
                forecast_date,
                projected_sales,
                projected_sales_low,
                projected_sales_high,
                required_labor_hours,
                labor_budget,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            forecast_date,
            projected_sales,
            projected_sales_low,
            projected_sales_high,
            required_labor_hours,
            labor_budget,
            status
        ))

        self.conn.commit()


    def get_forecasts(self):
        """
        Retrieve generated forecasts.
        """

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Forecasts
            ORDER BY forecast_date
        """)

        rows = cursor.fetchall()

        return [
            self.row_to_forecast(row)
            for row in rows
        ]
        
    def get_range(self, start_date, end_date):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Forecasts
            WHERE forecast_date >= ?
              AND forecast_date <= ?
            ORDER BY forecast_date
        """, (start_date, end_date))

        rows = cursor.fetchall()

        return [
            self.row_to_forecast(row)
            for row in rows
        ]

    def get_forecast_by_date(self, forecast_date):

        forecasts = self.get_range(forecast_date, forecast_date)

        if not forecasts:
            return None

        return forecasts[0]

        
    def approve_forecast(self, forecast_id):

        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE Forecasts
            SET status = 'Approved'
            WHERE forecast_id = ?
        """, (forecast_id,))

        self.conn.commit()

    def update_forecast(self, forecast_id, projected_sales, labor_budget):

        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE Forecasts
            SET projected_sales = ?,
                labor_budget = ?
            WHERE forecast_id = ?
        """, (projected_sales, labor_budget, forecast_id))

        self.conn.commit()

    def update_draft_forecasts(self, labor_percent, uncertainty):

        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE Forecasts
            SET labor_percent = ?,
                uncertainty = ?
            WHERE status = ?
        """, (labor_percent, uncertainty, 'Draft')
        )

        self.conn.commit()