from dataclasses import (dataclass, fields)

@dataclass(frozen=True)
class Forecast:
    forecast_date: str
    projected_sales: float
    projected_sales_low: float
    projected_sales_high: float
    required_labor_hours: float
    labor_budget: float
    status: str
    forecast_id: int | None = None

    required_fields = {
        "forecast_date",
        "projected_sales",
        "projected_sales_low",
        "projected_sales_high",
        "labor_budget",
        "status",
        "forecast_id"
    }

