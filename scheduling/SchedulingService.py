from shared.exceptions import ValidationError


class SchedulingService:

    def __init__(self, repository):
        self.repository = repository

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

        return self.repository.create_staffing_requirement(
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

        existing_requirement = (
            self.repository.get_staffing_requirement_by_id(
                requirement_id
            )
        )

        if existing_requirement is None:
            raise ValidationError(
                "Staffing requirement not found."
            )

        return self.repository.update_staffing_requirement(
            requirement_id,
            required_count
        )