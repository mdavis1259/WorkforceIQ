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

        return cursor.fetchall()

    def get_forecast_by_date(self, forecast_date):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Forecasts
            WHERE forecast_date = ?
        """, (forecast_date,))

        return cursor.fetchone()

    def get_forecasts_from_date(self, start_date):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Forecasts
            WHERE forecast_date >= ?
            ORDER BY forecast_date
            LIMIT 14
        """, (start_date,))

        return cursor.fetchall()
        
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
            SET labor_percent = ?
            AND SET uncertainty = ?
            WHERE status = ?
        """, (labor_percent, uncertainty, 'Draft')
        )

        self.conn.commit()