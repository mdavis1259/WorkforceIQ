from dataclasses import (dataclass, fields)

@dataclass(frozen=True)
class ShiftRequirement:
    role_name: str
    required_count: int

@dataclass(frozen=True)
class ShiftAssignment:
    assignment_id: int = None
    schedule_id: int = None
    employee_id: int = None
    role_id: int = None
    shift_id: int = None
    schedule_date: str = ""
    employee_name: str = ""
    role_name: str = ""
    hours: float = 0

    def __getitem__(self, key):
        return getattr(self, key)
@dataclass(frozen=True)
class StaffingRequirement:
    day_name: str = ""
    shift_name: str = ""
    role_name: str = ""
    workday_id: int = None
    shift_id: int = None
    role_id: int = None
    required_count: int = 0

    def __getitem__(self, key):
        return getattr(self, key)
