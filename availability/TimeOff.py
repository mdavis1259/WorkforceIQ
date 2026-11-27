from dataclasses import dataclass

@dataclass(frozen=True)
class TimeOff:
    employee_id: int
    start_date: str
    end_date: str
    status: str
    request_id: int | None = None

    required_fields = {
        "employee_id",
        "start_date",
        "end_date",
        "status",
        "request_id"
    }
