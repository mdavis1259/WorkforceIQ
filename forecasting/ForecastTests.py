"""
Forecast Module Tests

Validates the ForecastService business logic and forecasting
workflow used by WorkforceIQ.

Tests verify:

- 14-day forecast generation
- Forecast date generation
- Uncertainty range calculations
- Labor budget calculations
- Forecast structure integrity
"""

import unittest
from dataclasses import fields
from forecasting.ForecastService import ForecastService
from errors import InsufficientHistoryError

class MockForecastRepository:
    """
    Mock repository used to isolate ForecastService
    from the database during unit testing.
    """

    def __init__(self):
        self.saved_forecasts = []

    def get_demand_history(self):
        history = []

        for i in range(56):
            history.append({ "sales_amount": 4500 + (i * 10) })

        return history

    def clear_forecasts(self):
        self.saved_forecasts = []

    def get_forecast_by_date(self, forecast_date):
        return None

    def get_forecasts_from_date(self, start_date):
        return self.saved_forecasts

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
        self.saved_forecasts.append({
            "forecast_date": forecast_date,
            "projected_sales": projected_sales,
            "projected_sales_low": projected_sales_low,
            "projected_sales_high": projected_sales_high,
            "labor_budget": labor_budget,
            "status": "Draft"
        })


class ForecastServiceTests(unittest.TestCase):

    def setUp(self):
        repository = MockForecastRepository()
        self.service = ForecastService(repository)

    def test_generate_two_week_forecast_returns_14_days(self):
        """
        ForecastService should generate
        exactly 14 forecast records.
        """

        forecasts = self.service.generate_draft_forecast()

        self.assertEqual(len(forecasts), 14)

    def test_forecast_contains_dates(self):
        """
        Each forecast should contain
        a forecast date.
        """

        forecasts = self.service.generate_draft_forecast()

        self.assertTrue(
            hasattr(forecasts[0], "forecast_date")
        )

    def test_forecast_contains_projected_sales(self):
        """
        Each forecast should contain
        projected sales.
        """

        forecasts = self.service.generate_draft_forecast()

        self.assertTrue(
            hasattr(forecasts[0], "projected_sales")
        )

    def test_forecast_contains_uncertainty_values(self):
        """
        Each forecast should contain
        upper and lower uncertainty bounds.
        """

        forecasts = self.service.generate_draft_forecast()

        self.assertTrue(
            hasattr(forecasts[0], "projected_sales_low")
        )

        self.assertTrue(
            hasattr(forecasts[0], "projected_sales_high")
        )

    def test_low_estimate_is_less_than_prediction(self):
        """
        Lower forecast bound should be
        less than projected sales.
        """

        forecasts = self.service.generate_draft_forecast()

        self.assertLess(
            forecasts[0].projected_sales_low,
            forecasts[0].projected_sales
        )

    def test_high_estimate_is_greater_than_prediction(self):
        """
        Upper forecast bound should be
        greater than projected sales.
        """

        forecasts = self.service.generate_draft_forecast()

        self.assertGreater(
            forecasts[0].projected_sales_high,
            forecasts[0].projected_sales
        )

    def test_forecast_contains_labor_budget(self):
        """
        Forecast should include
        projected labor budget.
        """

        forecasts = self.service.generate_draft_forecast()

        self.assertTrue(
            hasattr(forecasts[0], "labor_budget")
        )

    def test_labor_budget_is_positive(self):
        """
        Labor budget should always
        be greater than zero.
        """

        forecasts = self.service.generate_draft_forecast()

        self.assertGreater(
            forecasts[0].labor_budget,
            0
        )

    def test_all_forecasts_have_same_structure(self):
        """
        Every generated forecast should
        contain the expected fields.
        """

        forecasts = self.service.generate_draft_forecast()

        required_fields = {
            "forecast_date",
            "projected_sales",
            "projected_sales_low",
            "projected_sales_high",
            "labor_budget",
            "status",
        }

        for forecast in forecasts:

            forecast_fields = {
                field.name
                for field in fields(forecast)
            }

            self.assertTrue(required_fields.issubset(forecast_fields))

    def test_forecasts_are_persisted(self):

        class MockForecastRepository:

            def __init__(self):
                self.saved = []

            def get_forecast_by_date(self, forecast_date):
                return None


            def get_demand_history(self):
                history = []

                for i in range(56):
                    history.append({ "sales_amount": 4500 + (i * 10) })

                return history

            def clear_forecasts(self):
                self.saved = []

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
                self.saved.append(
                    forecast_date
                )

        repository = MockForecastRepository()

        service = ForecastService(repository)

        service.generate_draft_forecast()

        self.assertEqual(
            len(repository.saved),
            14
        )

    def test_insufficient_history_raises_error(self):
        class MockForecastRepository:
            def get_demand_history(self):
                return [{ "sales_amount": 4500}] * 10

        service = ForecastService(MockForecastRepository())

        with self.assertRaises(
            InsufficientHistoryError
        ):
            service.generate_draft_forecast()

if __name__ == "__main__":
    unittest.main()