from dataclasses import (dataclass, fields)

# Rules: Date must be in an unapproved week. Cost = hours x hourly rate.

@dataclass(frozen=True)
class Assignment:
    assignment_id: int
    schedule_date: str
    shift_id: str
    employee_id: str
    role_id: str
    hours: str
    projected_cost: str

