from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone

from errors import NotFoundError
from shared.exceptions import ValidationError

class AvailabilityService:
    TIME_OFF_COLORS = {
        'Approved': 'red',
        'Pending': 'yellow',
        'Cancelled': 'gray',
        'Viewed': 'gray'
    }

    def __init__(self, availability_repository, employee_service):
        self.availability_repository = availability_repository
        self.employee_service = employee_service

    # ==========================================
    # Static methods 
    # ==========================================

    # Convert an ISO time or local datetime string to the shifts' HH:MM format.
    @staticmethod
    def format_shift_time(value):
        if not isinstance(value, str):
            raise ValueError("Shift time must be an ISO time or datetime string")

        try:
            if "T" in value or " " in value:
                parsed = datetime.fromisoformat(value).timetz()
            else:
                parsed = time.fromisoformat(value)
        except ValueError as error:
            raise ValueError("Shift time must be an ISO time or datetime string") from error

        if parsed.tzinfo is not None:
            raise ValueError("Shift time must not include a time zone")
        if parsed.second or parsed.microsecond:
            raise ValueError("Shift time must be an exact minute")
        return parsed.strftime("%H:%M")

    @staticmethod
    def _local_event_datetime(data, field):
        value = data.get(field)
        offset = data.get(f"{field}_timezone_offset")
        if not isinstance(value, str):
            raise ValueError(f"{field} must be an ISO datetime")
        if type(offset) is not int or not -1439 <= offset <= 1439:
            raise ValueError(f"{field} timezone offset must be an integer in minutes")
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{field} must be an ISO datetime") from error
        if timestamp.tzinfo is None:
            raise ValueError(f"{field} must include a timezone")
        return timestamp.astimezone(timezone(-timedelta(minutes=offset)))

    # ==========================================
    # Instance Methods
    # ==========================================

    def get_availability_data(self):
        return self.availability_repository.get_availability_data()

    def get_availability(self):
        return self.get_availability_data()

    def get_availability_by_employee(self, employee_id):
        return self.availability_repository.get_availability_by_employee(employee_id)

    def get_employee_availability(self, employee_id):
        return self.get_availability_by_employee(employee_id)

    def get_time_off_by_employee(self, employee_id):
        return self.availability_repository.get_time_off_by_employee(employee_id)
    
    def list_employees(self, associates_only=False):
        employees = self.employee_service.list_employees()

        if associates_only:
            employees = [
                employee for employee in employees
                if self.employee_service.get_system_role(employee.role_id) == 1
            ]
        return employees


    def availability_db_to_events(self, employee_availability_data, time_off_data, employee_id):
        formatted_data = []
        background_data = []

        def as_calendar_time(value):
            return value.rsplit('T', 1)[-1] if 'T' in value else value

        def as_calendar_date(value):
            return value.split('T')[0] if 'T' in value else value

        def add_one_day(value):
            return (date.fromisoformat(value.split('T')[0]) + timedelta(days=1)).isoformat()

        def calendar_days(value):
            return [int(day.strip()) for day in value.split(',') if day.strip()]

        # Returns a sorted list of all approved days from the time off data
        def build_approved_days(time_off_data):
            days = set()
            for row in time_off_data:
                # Only approved days
                if row['status'] != 'Approved':
                    continue

                # Get start and end dates
                start = date.fromisoformat(row['start_date'].split('T')[0])
                # End date is one day later due to FullCalendar treating end dates as exclusive
                end = date.fromisoformat(row['end_date'].split('T')[0])
                day = start
                # Add each approved day to the list
                while day <= end:
                    days.add(day.isoformat())
                    day += timedelta(days=1)
            return sorted(days) 
        
        # First, get time off.x
        for row in time_off_data:
            if row['status'] == 'Cancelled' or row['status'] == 'Viewed':
                continue

            background_data.append({
                'id': row['request_id'],
                'title': f"Status: {row['status']}",
                'start': as_calendar_date(row['start_date']),
                # End date is one day later due to FullCalendar treating end dates as exclusive
                'end': add_one_day(row['end_date']),
                'allDay': True,
                'display': 'background',
                'color': 'red' if row['status'] == 'Approved' else 'yellow' if row['status'] == 'Pending' else 'gray'
            })

        # Generate all the events for active shifts and workdays where no availability is set
        for shift in self.availability_repository.get_active_shifts():
            for workday_id in self.availability_repository.get_active_workdays():
                if self.availability_repository.get_matching_availability(employee_id, workday_id, shift['shift_id']) is None:
                    formatted_data.append({
                        'id': None,
                        'title': shift['shift_name'],
                        'startTime': as_calendar_time(shift['start_time']),
                        'endTime': as_calendar_time(shift['end_time']),
                        'daysOfWeek': [0 if workday_id == 7 else workday_id],
                        'availability': 2,
                        'color': 'gray',
                    })

        # Set all saved availability for the given employee
        for item in employee_availability_data:
            formatted_data.append({
                'id': item['employee_availability_id'],
                'title': self.availability_repository.get_shift_name(item['shift_id']),
                'startTime': as_calendar_time(self.availability_repository.get_shift_start_time(item['shift_id'])),
                'endTime': as_calendar_time(self.availability_repository.get_shift_end_time(item['shift_id'])),
                'daysOfWeek': calendar_days(self.availability_repository.get_days_with_matching_availability(
                                            item['employee_availability_id'],
                                            item['shift_id'],
                                            item['availability'])),
                'availability': item['availability'],
                'color': 'green' if item['availability'] == 1 else 'gray' if item['availability'] == 2 else 'red',
            })

        return formatted_data, background_data, build_approved_days(time_off_data)

        # Update availability row to match new data provided by the user
    def update_availability(self, data, employee_id):
        print("In update_availability with data:", data)

        # Validate data is dict
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object")

        # Get availability
        availability = data.get("availability")
        print("Availability value:", availability)
        if type(availability) is not int or availability not in (0, 1, 2):
            raise ValueError("Availability must be 0, 1, or 2")

        # Get shift name
        shift_name = data.get("shift_name")
        print("Shift name:", shift_name)
        if not isinstance(shift_name, str) or not shift_name.strip():
            raise ValueError("Shift name is required")

        # Get shift start and end times
        start = self._local_event_datetime(data, "start")
        end = self._local_event_datetime(data, "end")
        start_time = self.format_shift_time(start.replace(tzinfo=None).isoformat())
        print("Start time:", start_time)
        end_time = self.format_shift_time(end.replace(tzinfo=None).isoformat())
        print("End time:", end_time)

        # Get shift row from repository using shift name and start/end times
        shift_row = self.availability_repository.get_shift(shift_name, start_time, end_time)
        if shift_row is None:
            print("Shift not found")
            raise ValueError("Shift not found")
        shift_id = shift_row["shift_id"]

        # Get workday ID from week day
        workday_id = start.isoweekday()
        print("Workday ID:", workday_id)

        # Get employee availability ID if it exists
        employee_availability_id = data.get("id")
        print("Employee availability ID:", employee_availability_id)

        # If it doesn't, create a new availability row
        if employee_availability_id in (None, "", "null", "None"):
            print("Creating new availability row")
            return self.create_availability(employee_id, shift_id, workday_id, availability)

       # Validate employee availability ID is a positive integer
        if (type(employee_availability_id) is not int
                and not (isinstance(employee_availability_id, str)
                         and employee_availability_id.isascii()
                         and employee_availability_id.isdigit())):
            raise ValueError("Availability ID must be a positive integer")
        employee_availability_id = int(employee_availability_id)
        if employee_availability_id <= 0:
            raise ValueError("Availability ID must be a positive integer")

        # Get existing availability row by ID
        row = self.availability_repository.get_availability_by_id(employee_availability_id)
        if (row is None or row["employee_id"] != employee_id
                or row["shift_id"] != shift_id or row["workday_id"] != workday_id):
            print("Existing availability row does not match employee, shift, or workday")
            return None

        # Edit availability row with new availability value
        self.availability_repository.update_availability(employee_availability_id, availability)
        return employee_availability_id

    # Creates a new row in availability
    def create_availability(self, employee_id, shift_id, workday_id, availability):
        # Check if matching availability already exists
        existing = self.availability_repository.get_matching_availability(
            employee_id, workday_id, shift_id
        )

        # If it exists, update it with the new availability value
        if existing is not None:
            self.availability_repository.update_availability(
                existing["employee_availability_id"], availability
            )
            return existing["employee_availability_id"]

        # If not, create a new availability row
        return self.availability_repository.create_availability(
            employee_id, shift_id, workday_id, availability
        )

    def is_employee_available(self, employee_id, workday_id, shift_id):
        availability_row = self.availability_repository.get_matching_availability(employee_id, workday_id, shift_id)
        if availability_row is None:
            return False
        return availability_row['availability'] == 1
    