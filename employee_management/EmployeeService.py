"""Business rules for the Employee Management module (SDS sections 8.6, 8.7).

Other modules call EmployeeService only. They never read the Employees,
Roles, Qualifications or EmployeeQualifications tables directly.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from errors import NotFoundError, ValidationError

MAX_NAME_LENGTH = 50
MAX_HOURLY_RATE = Decimal("500")
MIN_WEEKLY_HOURS = 1
MAX_WEEKLY_HOURS = 80
DEFAULT_MAX_HOURS = 40
DEFAULT_PREFERRED_HOURS = 32


@dataclass(frozen=True)
class Employee:
    """Read-only employee object (SDS section 8.7)."""

    employee_id: int
    first_name: str
    last_name: str
    role_id: int
    hourly_rate: float
    max_hours_per_week: int
    preferred_hours_per_week: int
    active: bool
    qualification_ids: tuple = ()

    def to_dict(self, include_rate=True):
        """Dictionary for JSON responses. The hourly rate is hidden from
        the Employee role, so callers pass include_rate=False for them."""
        data = {
            "employee_id": self.employee_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "role_id": self.role_id,
            "max_hours_per_week": self.max_hours_per_week,
            "preferred_hours_per_week": self.preferred_hours_per_week,
            "active": self.active,
            "qualification_ids": list(self.qualification_ids),
        }
        if include_rate:
            data["hourly_rate"] = self.hourly_rate
        return data


class EmployeeService:
    def __init__(self, repository):
        self.repository = repository

    # ----- reads --------------------------------------------------
    def list_employees(self, search=None, include_inactive=False):
        search = (search or "").strip() or None
        rows = self.repository.list_employees(search, include_inactive)
        links = self.repository.get_all_qualification_ids()
        return [self._to_employee(row, links.get(row["employee_id"], []))
                for row in rows]

    def get_employee(self, employee_id):
        row = self.repository.get_employee(employee_id)
        if row is None:
            raise NotFoundError(f"Employee {employee_id} was not found.")
        qualification_ids = self.repository.get_qualification_ids(employee_id)
        return self._to_employee(row, qualification_ids)

    def list_roles(self):
        return self.repository.list_roles()

    def list_qualifications(self):
        return self.repository.list_qualifications()

    # ----- writes -------------------------------------------------
    def create_employee(self, data):
        """Create an employee. data may include qualification_ids."""
        clean = self._validate(data)
        qualification_ids = self._validate_qualification_ids(
            data.get("qualification_ids", [])
        )
        try:
            employee_id = self.repository.insert_employee(clean)
            self.repository.replace_qualifications(employee_id, qualification_ids)
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise
        return self.get_employee(employee_id)

    def update_employee(self, employee_id, data):
        """Update an employee. If data has qualification_ids, they replace
        the current ones; if it does not, the current ones are kept."""
        self.get_employee(employee_id)  # raises NotFoundError
        clean = self._validate(data)
        qualification_ids = None
        if "qualification_ids" in data:
            qualification_ids = self._validate_qualification_ids(
                data["qualification_ids"]
            )
        try:
            self.repository.update_employee(employee_id, clean)
            if qualification_ids is not None:
                self.repository.replace_qualifications(
                    employee_id, qualification_ids
                )
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise
        return self.get_employee(employee_id)

    def deactivate_employee(self, employee_id):
        """Soft delete: sets active = false so past schedules stay correct."""
        if not self.repository.set_active(employee_id, False):
            self.repository.rollback()
            raise NotFoundError(f"Employee {employee_id} was not found.")
        self.repository.commit()

    def reactivate_employee(self, employee_id):
        """Undoes a deactivation. The same profile, wage, hours and
        qualifications come back; nothing was ever deleted."""
        if not self.repository.set_active(employee_id, True):
            self.repository.rollback()
            raise NotFoundError(f"Employee {employee_id} was not found.")
        self.repository.commit()
        return self.get_employee(employee_id)

    def set_qualifications(self, employee_id, qualification_ids):
        self.get_employee(employee_id)  # raises NotFoundError
        ids = self._validate_qualification_ids(qualification_ids)
        try:
            self.repository.replace_qualifications(employee_id, ids)
            self.repository.commit()
        except Exception:
            self.repository.rollback()
            raise
        return self.get_employee(employee_id)

    # ----- helpers ------------------------------------------------
    @staticmethod
    def _to_employee(row, qualification_ids):
        return Employee(
            employee_id=row["employee_id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            role_id=row["role_id"],
            hourly_rate=row["hourly_rate"],
            max_hours_per_week=row["max_hours_per_week"],
            preferred_hours_per_week=row["preferred_hours_per_week"],
            active=bool(row["active"]),
            qualification_ids=tuple(qualification_ids),
        )

    def _validate(self, data):
        """Check the SDS section 8.7 rules. Returns cleaned values or
        raises ValidationError listing every problem."""
        problems = []

        def problem(field, issue):
            problems.append({"field": field, "issue": issue})

        names = {}
        for field, label in (("first_name", "First name"),
                             ("last_name", "Last name")):
            value = data.get(field)
            value = value.strip() if isinstance(value, str) else ""
            if not value:
                problem(field, f"{label} is required.")
            elif len(value) > MAX_NAME_LENGTH:
                problem(field,
                        f"{label} must be 1 to {MAX_NAME_LENGTH} characters.")
            names[field] = value

        role_id = self._to_int(data.get("role_id"))
        if role_id is None:
            problem("role_id", "A job role is required.")
        elif not self.repository.role_exists(role_id):
            problem("role_id", "The selected job role does not exist.")

        rate = self._to_decimal(data.get("hourly_rate"))
        if rate is None:
            problem("hourly_rate", "Hourly rate must be a number.")
        elif rate <= 0 or rate > MAX_HOURLY_RATE:
            problem("hourly_rate",
                    f"Hourly rate must be greater than 0 and at most "
                    f"{MAX_HOURLY_RATE}.")

        max_hours = self._hours(data, "max_hours_per_week",
                                DEFAULT_MAX_HOURS, problem)
        preferred_default = (min(DEFAULT_PREFERRED_HOURS, max_hours)
                             if max_hours is not None
                             else DEFAULT_PREFERRED_HOURS)
        preferred = self._hours(data, "preferred_hours_per_week",
                                preferred_default, problem, minimum=0)
        if (max_hours is not None and preferred is not None
                and preferred > max_hours):
            problem("preferred_hours_per_week",
                    "Preferred hours cannot be more than max hours.")

        if problems:
            raise ValidationError(problems)

        return {
            "first_name": names["first_name"],
            "last_name": names["last_name"],
            "role_id": role_id,
            "hourly_rate": float(rate),
            "max_hours_per_week": max_hours,
            "preferred_hours_per_week": preferred,
        }

    def _hours(self, data, field, default, problem, minimum=MIN_WEEKLY_HOURS):
        raw = data.get(field)
        if raw is None or raw == "":
            return default
        value = self._to_int(raw)
        if value is None or value < minimum or value > MAX_WEEKLY_HOURS:
            problem(field,
                    f"Must be a whole number from {minimum} to "
                    f"{MAX_WEEKLY_HOURS}.")
            return None
        return value

    def _validate_qualification_ids(self, ids):
        if ids is None:
            ids = []
        if not isinstance(ids, (list, tuple, set)):
            raise ValidationError([{"field": "qualification_ids",
                                    "issue": "Must be a list of ids."}])
        clean = []
        for raw in ids:
            value = self._to_int(raw)
            if value is None:
                raise ValidationError([{"field": "qualification_ids",
                                        "issue": "Every id must be a whole number."}])
            clean.append(value)
        missing = set(clean) - self.repository.existing_qualification_ids(clean)
        if missing:
            raise ValidationError([{
                "field": "qualification_ids",
                "issue": f"Unknown qualification id(s): {sorted(missing)}."}])
        return sorted(set(clean))

    @staticmethod
    def _to_int(value):
        if isinstance(value, bool):
            return None
        try:
            as_decimal = Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            return None
        if as_decimal != as_decimal.to_integral_value():
            return None
        return int(as_decimal)

    @staticmethod
    def _to_decimal(value):
        if isinstance(value, bool) or value is None:
            return None
        try:
            result = Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            return None
        return result if result.is_finite() else None
