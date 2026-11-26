from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
import sqlite3

from errors import NotFoundError, ConflictError, InvalidStateError
from shared.exceptions import ValidationError
from availability.Availability import Availability
from availability.Shift import Shift
from availability.TimeOff import TimeOff
from datetime import datetime, date, timedelta

class AvailabilityService:
    TIME_OFF_COLORS = {
        'Approved': 'red',
        'Pending': 'yellow',
        'Cancelled': 'gray'
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
            raise ValidationError("Shift time must be an ISO time or datetime string")

        try:
            if "T" in value or " " in value:
                parsed = datetime.fromisoformat(value).timetz()
            else:
                parsed = time.fromisoformat(value)
        except ValueError:
            raise ValidationError("Shift time must be an ISO time or datetime string")
        if parsed.tzinfo is not None:
            raise ValidationError("Shift time must not include a time zone")
        if parsed.second or parsed.microsecond:
            raise ValidationError("Shift time must be an exact minute")
        return parsed.strftime("%H:%M")

    @staticmethod
    def _local_event_datetime(data, field):
        value = data.get(field)
        offset = data.get(f"{field}_timezone_offset")
        if not value or not isinstance(value, str):
            raise ValidationError(f"{field} must be an ISO datetime")
        if type(offset) is not int or not -1439 <= offset <= 1439:
            raise ValidationError(f"{field} timezone offset must be an integer in minutes")
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValidationError(f"{field} must be an ISO datetime") from error
        if timestamp.tzinfo is None:
            raise ValidationError(f"{field} must include a timezone")
        return timestamp.astimezone(timezone(-timedelta(minutes=offset)))


    @staticmethod
    def convert_db_error(errors, operation="database"):
        error_str = str(error)
        
        if isinstance(error, sqlite3.IntegrityError):
            if "UNIQUE" in error_str or "UNIQUE constraint failed" in error_str:
                raise ConflictError(f"Duplicate record: {operation} failed due to unique constraint violation")
            elif "FOREIGN KEY" in error_str or "foreign key constraint failed" in error_str:
                raise ValidationError([{"field": "reference", "issue": f"Referenced record does not exist ({operation})"}])
            elif "NOT NULL" in error_str:
                raise ValidationError([{"field": "value", "issue": f"Required field is missing ({operation})"}])
            else:
                raise ConflictError(f"Data conflict: {operation} failed - {error_str}")
        
        elif isinstance(error, sqlite3.OperationalError):
            raise ValidationError([{"field": "database", "issue": f"Database operation failed during {operation}: {error_str}"}])
        elif isinstance(error, sqlite3.Error):
            raise ValidationError([{"field": "database", "issue": f"Database error during {operation}: {error_str}"}])
        else:
            raise ValidationError([{"field": "database", "issue": f"Unexpected database error during {operation}: {error_str}"}])

    # Convert time-off object into calendar background event
    @staticmethod
    def time_off_event(time_off):
        return {
            'id': time_off.request_id,
            'title': f"Status: {time_off.status}",
            'start': time_off.start_date,
            'end': (date.fromisoformat(time_off.end_date) + timedelta(days=1)).isoformat(),
            'allDay': True,
            'display': 'background',
            'color': 'red' if time_off.status == 'Approved' else 'yellow' if time_off.status == 'Pending' else 'gray'
        }
    # ==========================================
    # API Methods (SDS 8.3)
    # ==========================================

    def get_weekly_grid(self, employee_id):
        """
        Get weekly availability grid for an employee.
        Returns list of dicts: {workday_id, shift_id, available}
        """
        if self.employee_service.get_employee(employee_id) is None:
            raise NotFoundError(f"Employee {employee_id} not found")

        availabilities = []

        # Loop through shift and workdays
        # TODO: Refactor to allow for shifts only on some days
        for shift in self.availability_repository.get_active_shifts():
            for workday_id in self.availability_repository.get_active_workdays(): 
                avail = self.availability_repository.get_matching_availability(employee_id, workday_id, shift.shift_id)
                # Return new object if no matching availability exists
                if avail is None:
                    try:
                        avail = self.availability_repository.create_availability(
                            employee_id, shift.shift_id, workday_id, 2
                        )
                        availabilities.append(avail)
                    except sqlite3.Error as e:
                        self.convert_db_error(e, "creating default availability entry")
                # Else append the object
                else:
                    availabilities.append(avail)

        return availabilities
    
    def replace_weekly_grid(self, employee_id, weekly_grid):
        """
        Replace entire availability grid for an employee.
        Unset entries will not be added.
        Each entry: {workday_id (1-7), shift_id, availability (0=Not available, 1=Available, 2=Unset)}
        """

        if self.employee_service.get_employee(employee_id) is None:
            raise NotFoundError(f"Employee {employee_id} not found")
        
        # Validate entries
        for entry in weekly_grid:
            workday_id = entry.get("workday_id")
            shift_id = entry.get("shift_id")
            available = entry.get("availability")
            
            if not isinstance(workday_id, int) or workday_id < 1 or workday_id > 7:
                raise ValidationError([{"field": "workday_id", "issue": "workday_id must be between 1 and 7"}])
            if not isinstance(shift_id, int) or shift_id <= 0:
                raise ValidationError([{"field": "shift_id", "issue": "shift_id must be a positive integer"}])
            if not isinstance(available, int) or available not in (0, 1, 2):
                raise ValidationError([{"field": "availability", "issue": "availability must be 0, 1, or 2"}])

        # Call single function to allow for rollback in case of errors
        return self.availability_repository.replace_weekly_grid(employee_id, weekly_grid)
    
    def is_available(self, employee_id, date_obj, shift_id):
        """
        Check if an employee is available on a specific date and shift.
        date_obj: date object
        Returns: boolean
        """
        workday_id = date_obj.isoweekday()
        availability_obj = self.availability_repository.get_matching_availability(employee_id, workday_id, shift_id)
        if availability_obj is None:
            return False
        if availability_obj.availability is None:
            raise InvalidStateError("Availability is not set for this shift")
        
        return availability_obj.availability == 1

    def list_available(self, date_obj, shift_id):
        """
        Get list of employees available for a specific date and shift.
        date_obj: date object
        Returns: list of dicts {employee_id, name, role}
        """
        workday_id = date_obj.isoweekday()
        all_availabilities = self.availability_repository.get_availability_data()
        
        available = [
            avail for avail in all_availabilities
            if avail.workday_id == workday_id and avail.shift_id == shift_id and avail.availability == 1
        ]
        
        result = []
        for avail in available:
            employee = self.employee_service.get_employee(avail.employee_id)
            if employee:
                result.append({
                    "employee_id": avail.employee_id,
                    "name": f"{employee.first_name} {employee.last_name}",
                    "role": employee.role_id
                })
        
        return result

    def decide_time_off(self, request_id, status):
        """
        Update time-off request status (Approved, Denied, Cancelled).
        status: "Approved", "Denied", or "Cancelled"
        Returns: boolean (success)
        Raises: InvalidStateError if request is not in Pending state
        """
        if status not in ("Approved", "Denied", "Cancelled"):
            raise ValidationError([{"field": "status", "issue": "status must be 'Approved', 'Denied', or 'Cancelled'"}])
        
        # Get the request to check its current status
        time_off = self.availability_repository.get_time_off_request_by_id(request_id)
        if time_off is None:
            raise NotFoundError(f"Time-off request {request_id} not found")
        
        if time_off.status != "Pending":
            raise InvalidStateError(f"Request is {time_off.status}, not Pending")
        
        success = self.availability_repository.update_time_off_request_by_id(request_id, status)
        if not success:
            raise InvalidStateError("Could not update request status")
        
        return success


    # ==========================================
    # Availability Methods
    # ==========================================

    def get_availability(self):
        return self.availability_repository.get_availability()

    def get_availability_by_employee(self, employee_id):
        try:
            return self.availability_repository.get_availability_by_employee(employee_id)
        except sqlite3.Error as e:
            self.convert_db_error(e, "retrieving employee availabilities")

    def get_time_off_by_employee(self, employee_id):
        return self.availability_repository.get_time_off_by_employee(employee_id)

    def get_time_off_request(self, request_id, employee_id):
        return self.availability_repository.get_time_off_request(request_id, employee_id)

    def get_time_off_review(self, request_id, employee_id):
        time_off = self.get_time_off_request(request_id, employee_id)
        if time_off is None:
            return None
        start = date.fromisoformat(time_off.start_date[:10])
        end = date.fromisoformat(time_off.end_date[:10])
        employee = self.employee_service.get_employee(employee_id)
        return {
            "id": time_off.request_id,
            "employee_name": f"{employee.first_name} {employee.last_name}",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "status": time_off.status,
        }

    def review_time_off_request(self, request_id, employee_id, data):
        if not isinstance(data, dict) or data.get("status") not in ("Approved", "Denied"):
            raise ValidationError("Status must be Approved or Denied")
        return self.availability_repository.update_pending_time_off(
            request_id, employee_id, data["status"]
        )

    # Creates a new time-off request from JSON data and current user's employee ID
    def create_time_off_request(self, data, employee_id):
        # Validate employee ID
        if employee_id is None:
            raise ValidationError("Employee ID is required")
        if type(employee_id) is not int:
            raise ValidationError("Invalid Employee ID")
        employee = self.employee_service.get_employee(employee_id)
        if employee is None:
            raise ValidationError("Invalid Employee ID")
        
        # Validate data (we already know its a dict)
        if not "start_date" in data or not "end_date" in data:
            raise ValidationError("Both start_date and end_date are required")

        # Get date strings
        dates = []
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        # Validate and parse date strings
        for field in ("start_date", "end_date"):
            # Validate 
            value = data.get(field)
            if value is None:
                raise ValidationError(f"{field} is required")
            if not isinstance(value, str):
                raise ValidationError(f"{field} must be a date in YYYY-MM-DD format")
           
            try:
                parsed = datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                # String is not in right format
                raise ValidationError(f"{field} must be a date in YYYY-MM-DD format")
            
            # Append the parsed date to the list of dates
            dates.append(parsed)

        start, end = dates
        today = date.today()
        # Validate that start and end dates are not in the past and are in correct order
        if start < today or end < today:
            raise ValidationError("Start Date and End Date must be today or later")
        if end < start:
            raise ValidationError("End Date must be on or after Start Date")
        if start < today:
            raise ValidationError("Start Date must be today or later")
        if end < today:
            raise ValidationError("End Date must be today or later")
        if end >= date.max:
            raise ValidationError("End Date is too far in the future")

        # Validate the range does not overlap any existing time-off requests
        if self.availability_repository.check_time_off_overlap(employee_id, start_date, end_date):
            raise ConflictError("Dates overlap an existing time-off request")

        # Create the time-off request in the repository
        time_off = self.availability_repository.create_time_off_request(
            employee_id, start_date, end_date
        )

        # Convert to calendar event format and return it
        return self.time_off_event(time_off)

    @staticmethod
    def split_background_event(event):
        first_day_end = (date.fromisoformat(event['start']) + timedelta(days=1)).isoformat()
        first_day = {**event, 'end': first_day_end}
        if first_day_end >= event['end']:
            return [first_day]
        return [first_day, {**event, 'start': first_day_end, 'title': ''}]
    
    def list_employees(self, associates_only=False):
        employees = self.employee_service.list_employees()

        if not employees:
            return []

        if associates_only:
            employees = [
                employee for employee in employees
                if self.employee_service.get_system_role(employee.employee_id) == 1
            ]
        return employees


    def availability_db_to_events(self, employee_availability_data, time_off_data, employee_id):
        formatted_data = []
        background_data = []

        def as_calendar_time(value):
            return value.rsplit('T', 1)[-1] if 'T' in value else value

        # Returns a sorted list of all approved days from the time off data
        def build_approved_days(time_off_data):
            days = set()
            for time_off in time_off_data:
                # Only approved days
                if time_off.status != 'Approved':
                    continue

                # Get start and end dates
                start = date.fromisoformat(time_off.start_date.split('T')[0])
                # End date is one day later due to FullCalendar treating end dates as exclusive
                end = date.fromisoformat(time_off.end_date.split('T')[0])
                day = start
                # Add each approved day to the list
                while day <= end:
                    days.add(day.isoformat())
                    day += timedelta(days=1)
            return sorted(days) 
        
        # First, get time off
        for time_off in time_off_data:
            if time_off.status == 'Cancelled' or time_off.status == 'Viewed':
                continue

            background_data.append(self.time_off_event(time_off))

        # Generate all the events for active shifts and workdays where no availability is set
        for shift in self.availability_repository.get_active_shifts():
            for workday_id in self.availability_repository.get_active_workdays():
                if self.availability_repository.get_matching_availability(employee_id, workday_id, shift.shift_id) is None:
                    formatted_data.append({
                        'id': None,
                        'title': shift.shift_name,
                        'startTime': as_calendar_time(shift.start_time),
                        'endTime': as_calendar_time(shift.end_time),
                        'daysOfWeek': [0 if workday_id == 7 else workday_id],
                        'availability': 2,
                        'color': 'gray',
                    })

        # Set all saved availability for the given employee
        for item in employee_availability_data:
            formatted_data.append({
                'id': item.employee_availability_id,
                'title': self.availability_repository.get_shift_name(item.shift_id),
                'startTime': as_calendar_time(self.availability_repository.get_shift_start_time(item.shift_id)),
                'endTime': as_calendar_time(self.availability_repository.get_shift_end_time(item.shift_id)),
                'daysOfWeek': [0 if item.workday_id == 7 else item.workday_id],
                'availability': item.availability,
                'color': 'green' if item.availability == 1 else 'gray' if item.availability == 2 else 'red',
            })

        return formatted_data, background_data, build_approved_days(time_off_data)

    # Update availability row to match new data provided by the user
    def update_availability(self, data, employee_id):
        # Validate data is dict
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object")

        # Get availability
        availability = data.get("availability")
        if type(availability) is not int or availability not in (0, 1, 2):
            raise ValidationError("Availability must be 0, 1, or 2")

        # Get shift name
        shift_name = data.get("shift_name")
        if not isinstance(shift_name, str) or not shift_name.strip():
            raise ValidationError("Shift name is required")

        # Get shift start and end times
        start = self._local_event_datetime(data, "start")
        end = self._local_event_datetime(data, "end")
        start_time = self.format_shift_time(start.replace(tzinfo=None).isoformat())
        end_time = self.format_shift_time(end.replace(tzinfo=None).isoformat())

        # Get shift from repository using shift name and start/end times
        shift = self.availability_repository.get_shift(shift_name, start_time, end_time)
        if shift is None:
            raise NotFoundError("Shift not found")
        shift_id = shift.shift_id

        # Get workday ID from week day
        workday_id = start.isoweekday()

        # Get employee availability ID if it exists
        employee_availability_id = data.get("id")

        # If it doesn't, create a new availability row
        if employee_availability_id in (None, "", "null", "None"):
            return self.create_availability(employee_id, shift_id, workday_id, availability)

        # Validate employee availability ID is a positive integer
        if not isinstance(employee_availability_id, int):
            try:
                employee_availability_id = int(employee_availability_id)
            except (TypeError, ValueError):
                raise ValidationError("Availability ID must be a positive integer")
        
        if employee_availability_id <= 0:
            raise ValidationError("Availability ID must be a positive integer")

        # Get existing availability row by ID
        availability_obj = self.availability_repository.get_availability_by_id(employee_availability_id)
        if (availability_obj is None or availability_obj.employee_id != employee_id
                or availability_obj.shift_id != shift_id or availability_obj.workday_id != workday_id):
            return None

        # Update availability row with new availability value
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
                existing.employee_availability_id, availability
            )
            return existing.employee_availability_id

        # If not, create a new availability row
        try:
            availability_obj = self.availability_repository.create_availability(
                employee_id, shift_id, workday_id, availability
            )
        except sqlite3.Error as e:
            self.convert_db_error(e, "creating availability entry")
        return availability_obj.employee_availability_id

    def get_available_employees_for_shift(self, workday_id, shift_id):
        # TODO: GO through API to get employees
        employees = self.employee_service.list_employees()
        available_employees = []
        if employees is None:
            raise NotFoundError("Failed to retrieve employees")
        for employee in employees:
            if not employee.is_active:
                continue
            if employee.employee_id is None:
                raise InvalidStateError("Employee ID is missing")
            if self.is_employee_available(employee.employee_id, workday_id, shift_id):
                available_employees.append(employee)
        return available_employees
    
    def is_employee_available(self, employee_id, workday_id, shift_id):
        availability_obj = self.availability_repository.get_matching_availability(employee_id, workday_id, shift_id)
        if availability_obj is None:
            return False
        if availability_obj.availability is None:
            raise InvalidStateError("Availability is not set for this shift")
        return availability_obj.availability == 1