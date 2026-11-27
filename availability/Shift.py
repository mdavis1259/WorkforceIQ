from dataclasses import dataclass

@dataclass(frozen=True)
class Shift:
    shift_name: str
    start_time: str
    end_time: str
    shift_id: int | None = None
    active: int | None = None

    required_fields = {
        "shift_name",
        "start_time",
        "end_time",
        "shift_id"
    }
