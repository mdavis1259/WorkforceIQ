from dataclasses import (dataclass, fields)

@dataclass(frozen=True)
class Schedule:
    week_start: str
    status: str
    schedule_id: int=None