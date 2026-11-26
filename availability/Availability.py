from dataclasses import dataclass

@dataclass(frozen=True)
class Availability:
    employee_id: int
    shift_id: int
    workday_id: int
    availability: int
    employee_availability_id: int | None = None

    required_fields = {
        "employee_id",
        "shift_id",
        "workday_id",
        "availability"
    }
