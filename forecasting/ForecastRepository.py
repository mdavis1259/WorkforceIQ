class ForecastRepository:
    def __init__(self, conn):
        self.conn = conn

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


    def save_forecast(
        self,
        forecast_date,
        projected_sales,
        projected_sales_low,
        projected_sales_high,
        required_labor_hours,
        labor_budget,
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
                labor_budget
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            forecast_date,
            projected_sales,
            projected_sales_low,
            projected_sales_high,
            required_labor_hours,
            labor_budget,
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

        return cursor.fetchall()