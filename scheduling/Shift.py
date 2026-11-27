from dataclasses import (dataclass, fields)

@dataclass(frozen=True)
class ShiftRequirement:
    role_name: str
    required_count: int

@dataclass(frozen=True)
class ShiftAssignment:
    employee_name: str
    role_name: str
    hours: float