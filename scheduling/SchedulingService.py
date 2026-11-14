from shared.exceptions import ValidationError
from datetime import datetime, timedelta

class SchedulingService:

    def __init__(self, repository, availability_service=None):
        self.repository = repository
        self.availability_service = availability_service

    # ==========================================
    # SHIFTS
    # ==========================================

    def list_shifts(self):

        return self.repository.get_shifts()

    def create_shift(
        self,
        shift_name,
        start_time,
        end_time
    ):

        if not shift_name:
            raise ValidationError(
                "Shift name is required."
            )

        if not start_time:
            raise ValidationError(
                "Start time is required."
            )

        if not end_time:
            raise ValidationError(
                "End time is required."
            )

        return self.repository.create_shift(
            shift_name,
            start_time,
            end_time
        )

    def update_shift(
        self,
        shift_id,
        shift_name,
        start_time,
        end_time
    ):

        if shift_id is None:
            raise ValidationError(
                "Shift ID is required."
            )

        if not shift_name:
            raise ValidationError(
                "Shift name is required."
            )

        if not start_time:
            raise ValidationError(
                "Start time is required."
            )

        if not end_time:
            raise ValidationError(
                "End time is required."
            )

        existing_shift = (
            self.repository.get_shift_by_id(
                shift_id
            )
        )

        if existing_shift is None:
            raise ValidationError(
                "Shift not found."
            )

        return self.repository.update_shift(
            shift_id,
            shift_name,
            start_time,
            end_time
        )

    def delete_shift(self, shift_id):

        if shift_id is None:
            raise ValidationError("Shift ID is required.")

        existing_shift = self.repository.get_shift_by_id(shift_id)

        if existing_shift is None:
            raise ValidationError("Shift not found.")

        self.repository.delete_shift(shift_id)

    # ==========================================
    # STAFFING REQUIREMENTS
    # ==========================================

    def list_staffing_requirements(self):

        return self.repository.get_staffing_requirements()

    def create_staffing_requirement(
        self,
        workday_id,
        shift_id,
        role_id,
        required_count
    ):

        if workday_id is None:
            raise ValidationError(
                "Workday is required."
            )

        if shift_id is None:
            raise ValidationError(
                "Shift is required."
            )

        if role_id is None:
            raise ValidationError(
                "Role is required."
            )

        if required_count is None:
            raise ValidationError(
                "Required count is required."
            )

        if int(required_count) < 1:
            raise ValidationError(
                "Required count must be greater than zero."
            )

        if self.repository.staffing_requirement_exists(workday_id, shift_id, role_id):
            return None

        return self.repository.create_staffing_requirement(
            workday_id,
            shift_id,
            role_id,
            required_count
        )

    def update_staffing_requirement(
        self,
        shift_id,
        role_id,
        required_count
    ):

        if shift_id is None:
            raise ValidationError(
                "Shift ID is required."
            )

        if role_id is None:
            raise ValidationError(
                "Role ID is required."
            )

        if required_count is None:
            raise ValidationError(
                "Required count is required."
            )

        if int(required_count) < 1:
            raise ValidationError(
                "Required count must be greater than zero."
            )

        return self.repository.update_staffing_requirement(
            shift_id,
            role_id,
            required_count
        )

    def delete_staffing_requirement(
        self,
        shift_id,
        role_id
    ):

        if shift_id is None:
            raise ValidationError(
                "Shift ID is required."
            )

        if role_id is None:
            raise ValidationError(
                "Role ID is required."
            )

        self.repository.delete_staffing_requirement(shift_id, role_id)

    # ==================================================
    # WORKDAYS
    # ==================================================

    def list_workdays(self):

        return self.repository.get_workdays()

    def update_workday(self, workday_id, active):
        
        if workday_id is None:
            raise ValidationError("Workday ID is required.")

        existing = self.repository.get_workday_by_id(workday_id)

        if existing is None:
            raise ValidationError("Workday not found.")

        return self.repository.update_workday(workday_id, active)

    # ===================================================
    # SCHEDULE GENERATION
    # ===================================================

    def create_schedule(self, week_start):
        
        if not week_start:
            raise ValidationError("Week start date is required.")

        return self.repository.create_schedule(week_start)

    def get_schedule(self, week_start):

        return self.repository.get_schedule_by_week(week_start)
    
    def get_schedule_date(self, week_start, workday_id):
        start = datetime.fromisoformat(week_start).date()

        schedule_date = (start + timedelta(days=workday_id - 1))

        return schedule_date.isoformat()

    def generate_week(self, week_start):

        schedule = self.create_schedule(week_start)
        
        requirements = (self.repository.get_staffing_requirement_rows())

        for requirement in requirements:

            schedule_date = self.get_schedule_date(week_start, requirement["workday_id"])

            employees = self.repository.get_employees_by_role(requirement["role_id"])
            
            if not employees:
                continue

            candidate_employees = employees

            # Emplyee Availability Filter
            if self.availability_service:

                candidate_employees = [
                    employee
                    for employee in candidate_employees
                    if self.availability_service.is_employee_available(
                        employee["employee_id"],
                        schedule_date,
                        requirement["shift_id"]
                    )
                ]

            # Weekly hour limit filter
            candidate_employees = [
                employee
                for employee in candidate_employees
                if (self.repository.get_employee_hours_for_week(
                    employee["employee_id"], week_start) + 8 <= employee["max_hours_per_week"])]

            if not candidate_employees:
                continue

            employee = candidate_employees[0]

            self.create_assignment(
                schedule["schedule_id"],
                employee["employee_id"],
                requirement["role_id"],
                requirement["shift_id"],
                schedule_date,
                8
            )

        return schedule
    
    # ===================================================
    # ASSIGNMENTS
    # ===================================================
    def create_assignment(
        self,
        schedule_id,
        employee_id,
        role_id,
        shift_id,
        schedule_date,
        hours
    ):
        if schedule_id is None:
            raise ValidationError("Schedule ID is required.")

        return self.repository.create_assignment(
            schedule_id,
            employee_id,
            role_id,
            shift_id,
            schedule_date,
            hours
        )

    def get_assignments(
        self,
        schedule_id
    ):
        return self.repository.get_assignments(schedule_id)
    