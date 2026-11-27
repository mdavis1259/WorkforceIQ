from shared.exceptions import ValidationError
from datetime import datetime, timedelta

class SchedulingService:

    def __init__(
        self, 
        scheduling_repository, 
        employee_service,
        forecasting_service,
        availability_service
    ):
        self.scheduling_repository = scheduling_repository
        self.employee_service = employee_service
        self.forecasting_service = forecasting_service
        self.availability_service = availability_service

    # ==========================================
    # SHIFTS
    # ==========================================

    def list_shifts(self):

        return self.scheduling_repository.get_shifts()

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

        return self.scheduling_repository.create_shift(
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
            self.scheduling_repository.get_shift_by_id(
                shift_id
            )
        )

        if existing_shift is None:
            raise ValidationError(
                "Shift not found."
            )

        return self.scheduling_repository.update_shift(
            shift_id,
            shift_name,
            start_time,
            end_time
        )

    def delete_shift(self, shift_id):

        if shift_id is None:
            raise ValidationError("Shift ID is required.")

        existing_shift = self.scheduling_repository.get_shift_by_id(shift_id)

        if existing_shift is None:
            raise ValidationError("Shift not found.")

        self.scheduling_repository.delete_shift(shift_id)

    # ==========================================
    # STAFFING REQUIREMENTS
    # ==========================================

    def list_staffing_requirements(self):

        return self.scheduling_repository.get_staffing_requirements()

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

        if self.scheduling_repository.staffing_requirement_exists(workday_id, shift_id, role_id):
            return None

        return self.scheduling_repository.create_staffing_requirement(
            workday_id,
            shift_id,
            role_id,
            required_count
        )

    def update_staffing_requirement(
        self,
        requirement_id,
        required_count
    ):

        if requirement_id is None:
            raise ValidationError(
                "Requirement ID is required."
            )

        if required_count is None:
            raise ValidationError(
                "Required count is required."
            )

        if int(required_count) < 1:
            raise ValidationError(
                "Required count must be greater than zero."
            )

        return self.scheduling_repository.update_staffing_requirement(
            requirement_id,
            required_count
        )

    def delete_staffing_requirement(
        self,
        requirement_id
    ):

        if requirement_id is None:
            raise ValidationError(
                "Requirement ID is required."
            )

        self.scheduling_repository.delete_staffing_requirement(requirement_id)

    # ==================================================
    # WORKDAYS
    # ==================================================

    def list_workdays(self):

        return self.scheduling_repository.get_workdays()

    def update_workday(self, workday_id, active):
        
        if workday_id is None:
            raise ValidationError("Workday ID is required.")

        existing = self.scheduling_repository.get_workday_by_id(workday_id)

        if existing is None:
            raise ValidationError("Workday not found.")

        return self.scheduling_repository.update_workday(workday_id, active)

    # ===================================================
    # SCHEDULE GENERATION
    # ===================================================

    def create_schedule(self, week_start):
        
        if not week_start:
            raise ValidationError("Week start date is required.")

        existing = self.get_schedule(week_start)
        if existing:
            return existing

        return self.scheduling_repository.create_schedule(week_start)

    def get_schedule(self, week_start):

        return self.scheduling_repository.get_schedule_by_week(week_start)
    
    def get_schedule_date(self, week_start, workday_id):
        start = datetime.fromisoformat(week_start).date()

        schedule_date = (start + timedelta(days=workday_id - 1))

        return schedule_date.isoformat()

    def generate_week(self, week_start):

        schedule = self.create_schedule(week_start)
        
        summary = {
            "requirements_processed": 0,
            "employees_considered": 0,
            "employees_assigned": 0,
            "unfilled_requirements": 0,
            "requirements": [],
            "daily_labor_cost": {},
            "daily_labor_budget": {},
            "daily_variance": {}
        }

        requirements = (self.scheduling_repository.get_staffing_requirement_rows())

        considered_employee_ids = set()

        for requirement in requirements:

            summary["requirements_processed"] += 1

            required_count = requirement["required_count"]

            schedule_date = self.get_schedule_date(week_start, requirement["workday_id"])

            employees = self.scheduling_repository.get_employees_by_role(requirement["role_id"])

            for employee in employees:
                considered_employee_ids.add(employee["employee_id"])

            summary["employees_considered"] = len(considered_employee_ids)

            assigned_count = 0

            if not employees:
                continue

            candidate_employees = employees

            # Employee Availability Filter
            candidate_employees = [
                employee
                for employee in candidate_employees
                if self.availability_service.is_employee_available(
                    employee["employee_id"],
                    requirement["workday_id"],
                    requirement["shift_id"]
                )
            ]

            # Weekly hour limit filter
            candidate_employees = [
                employee
                for employee in candidate_employees
                if (self.scheduling_repository.get_employee_hours_for_week(
                    employee["employee_id"], week_start) + 8 <= employee["max_hours_per_week"])]

            # Overlap filter
            candidate_employees = [
                employee
                for employee in candidate_employees
                if not self.scheduling_repository.has_overlapping_assignment(
                    employee["employee_id"],
                    schedule_date,
                    requirement["shift_id"]
                )
            ]

            if not candidate_employees:
                
                summary["unfilled_requirements"] += 1

                summary["requirements"].append({
                    "workday": requirement["day_name"],
                    "shift": requirement["shift_name"],
                    "role": requirement["role_name"],
                    "required_count": required_count,
                    "assigned_count": 0
                })

                continue

            for i in range(required_count):

                if not candidate_employees:
                    break

                employee = candidate_employees.pop(0)

                self.create_assignment(
                    schedule["schedule_id"],
                    employee["employee_id"],
                    requirement["role_id"],
                    requirement["shift_id"],
                    schedule_date,
                    8
                )

                print(
                    employee["first_name"],
                    employee["hourly_rate"],
                    schedule_date
                )

                labor_cost = employee["hourly_rate"] * 8

                if schedule_date not in summary["daily_labor_cost"]:
                    summary["daily_labor_cost"][schedule_date] = 0

                summary["daily_labor_cost"][schedule_date] += labor_cost

                assigned_count += 1
                summary["employees_assigned"] += 1

            if assigned_count < required_count:
                summary["unfilled_requirements"] += 1

            summary["requirements"].append({
                "workday": requirement["day_name"],
                "shift": requirement["shift_name"],
                "role": requirement["role_name"],
                "required_count": required_count,
                "assigned_count": assigned_count
            })

            forecasts = []

            if self.forecasting_service:
                forecasts = self.forecasting_service.get_forecasts()

            for forecast in forecasts:

                forecast_date = forecast.forecast_date

                if forecast_date in summary["daily_labor_cost"]:

                    budget = forecast.labor_budget

                    actual = summary["daily_labor_cost"][forecast_date]

                    summary["daily_labor_budget"][forecast_date] = budget

                    summary["daily_variance"][forecast_date] = round(budget - actual, 2)


        return schedule, summary
    
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

        return self.scheduling_repository.create_assignment(
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
        return self.scheduling_repository.get_assignments(schedule_id)
    
