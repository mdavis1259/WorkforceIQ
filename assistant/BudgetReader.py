"""BudgetReader: read-only weekly labor cost versus labor budget.

Reads the saved schedule and its assignments from SchedulingService and the
daily labor budget from ForecastService (SDS 8.6: modules call each other
only through services). It never writes. Only totals are returned, never an
individual employee's hourly rate.
"""
from datetime import date, timedelta


class BudgetReader:
    def __init__(self, load_schedule, load_assignments, load_forecasts):
        self._schedule = load_schedule        # (week_start) -> row or None
        self._assignments = load_assignments  # (schedule_id) -> rows
        self._forecasts = load_forecasts      # (start, end) -> Forecast list

    def weekly_budget(self, week_start):
        """Return None if no schedule exists for that week, otherwise a dict
        with per-day cost and budget, week totals, and within_budget
        (None when the forecast budget is missing for a staffed day)."""
        start = date.fromisoformat(week_start)
        schedule = self._schedule(start.isoformat())
        if not schedule:
            monday = start - timedelta(days=start.weekday())
            if monday != start:
                start = monday
                schedule = self._schedule(start.isoformat())
        if not schedule:
            return None

        days = [(start + timedelta(days=n)).isoformat() for n in range(7)]
        cost = {}
        count = 0
        for row in self._assignments(schedule["schedule_id"]):
            if row["schedule_date"] not in days:
                continue
            amount = round(float(row["hours"]) * float(row["hourly_rate"]), 2)
            cost[row["schedule_date"]] = round(
                cost.get(row["schedule_date"], 0) + amount, 2)
            count += 1

        forecasts = {f.forecast_date: f
                     for f in self._forecasts(days[0], days[-1])}
        rows, missing = [], []
        for day in days:
            budget = forecasts[day].labor_budget if day in forecasts else None
            if day not in cost and budget is None:
                continue
            if day in cost and budget is None:
                missing.append(day)
            spent = cost.get(day, 0.0)
            rows.append({
                "date": day,
                "labor_cost": spent,
                "labor_budget": budget,
                "variance": None if budget is None
                else round(budget - spent, 2),
            })

        total_cost = round(sum(r["labor_cost"] for r in rows), 2)
        total_budget = round(sum(r["labor_budget"] for r in rows
                                 if r["labor_budget"] is not None), 2)
        judged = bool(count) and not missing and any(
            r["labor_budget"] is not None for r in rows)
        return {
            "week_start": start.isoformat(),
            "has_assignments": bool(count),
            "days": rows,
            "projected_labor_cost": total_cost,
            "labor_budget": total_budget,
            "within_budget": (total_cost <= total_budget) if judged else None,
            "missing_forecast_days": missing,
            "draft_forecast": any(
                getattr(forecasts[r["date"]], "status", "") != "Approved"
                for r in rows if r["date"] in forecasts),
        }


def build_default_budget():
    """Wire BudgetReader to the real services. Needs a Flask app context."""
    from database.connection import get_db_connection
    from employee_management.EmployeeRepository import EmployeeRepository
    from employee_management.EmployeeService import EmployeeService
    from forecasting.ForecastRepository import ForecastRepository
    from forecasting.ForecastService import ForecastService
    from scheduling.SchedulingRepository import SchedulingRepository
    from scheduling.SchedulingService import SchedulingService
    from availability.AvailabilityRepository import AvailabilityRepository
    from availability.AvailabilityService import AvailabilityService

    def with_service(call):
        connection = get_db_connection()
        try:
            employees = EmployeeService(EmployeeRepository(connection))
            forecasting = ForecastService(ForecastRepository(connection))
            availability = AvailabilityService(
                AvailabilityRepository(connection), employees)
            scheduling = SchedulingService(
                SchedulingRepository(connection), employees, forecasting,
                availability)
            return call(scheduling, forecasting)
        finally:
            connection.close()

    return BudgetReader(
        load_schedule=lambda w: with_service(lambda s, f: s.get_schedule(w)),
        load_assignments=lambda sid: with_service(
            lambda s, f: s.get_assignments(sid)),
        load_forecasts=lambda a, b: with_service(
            lambda s, f: f.get_range(a, b)),
    )
