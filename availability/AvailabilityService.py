from datetime import date, datetime, time, timedelta, timezone
import sqlite3

from shared.exceptions import NotFoundError, ConflictError, InvalidStateError, PermissionDeniedError, ValidationError
from flask_login import current_user

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
    # Utility & Static Methods
    # ==========================================

    @staticmethod
    def _format_shift_time(value):
        """Convert an ISO time or local datetime string to the shifts' HH:MM format."""
        if not isinstance(value, str):
            raise ValidationError([{"field": "shift_time", "issue": "must be an ISO time or datetime string"}])

        try:
            if "T" in value or " " in value:
                parsed = datetime.fromisoformat(value).timetz()
            else:
                parsed = time.fromisoformat(value)
        except ValueError:
            raise ValidationError([{"field": "shift_time", "issue": "must be an ISO time or datetime string"}])
        if parsed.tzinfo is not None:
            raise ValidationError([{"field": "shift_time", "issue": "must not include a time zone"}])
        if parsed.second or parsed.microsecond:
            raise ValidationError([{"field": "shift_time", "issue": "must be an exact minute"}])
        return parsed.strftime("%H:%M")

    @staticmethod
    def _local_event_datetime(data, field):
        """Extract local event datetime with timezone offset validation."""
        value = data.get(field)
        offset = data.get(f"{field}_timezone_offset")
        if not value or not isinstance(value, str):
            raise ValidationError([{"field": field, "issue": "must be an ISO datetime"}])
        if type(offset) is not int or not -1439 <= offset <= 1439:
            raise ValidationError([{"field": field, "issue": "timezone offset must be an integer in minutes"}])
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValidationError([{"field": field, "issue": "must be an ISO datetime"}]) from error
        if timestamp.tzinfo is None:
            raise ValidationError([{"field": field, "issue": "must include a timezone"}])
        return timestamp.astimezone(timezone(-timedelta(minutes=offset)))

    @staticmethod
    def _convert_db_error(error, operation="database"):
        """Convert database errors to domain-specific exceptions."""
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

    @staticmethod
    def _time_off_event(time_off):
        """Convert time-off object into calendar background event."""
        try:
            return {
                'id': time_off.request_id,
                'title': f"Status: {time_off.status}",
                'start': time_off.start_date,
                'end': (date.fromisoformat(time_off.end_date) + timedelta(days=1)).isoformat(),
                'allDay': True,
                'display': 'background',
                'color': 'red' if time_off.status == 'Approved' else 'yellow' if time_off.status == 'Pending' else 'gray'
            }
        except (ValueError, AttributeError) as e:
            raise InvalidStateError(f"Invalid time-off event data: {e}")

    @staticmethod
    def _as_calendar_time(value):
        """Extract time portion from datetime string."""
        return value.rsplit('T', 1)[-1] if 'T' in value else value

    @staticmethod
    def _validate_time_off(time_off):
        """Validate time-off object has required attributes."""
        if time_off is None:
            raise InvalidStateError("Time off object is None")
        if not isinstance(time_off, object):
            raise InvalidStateError("Time off is not a valid object")
        for attribute in 'status', 'start_date', 'end_date':
            if not hasattr(time_off, attribute):
                raise InvalidStateError(f"Time off object is missing '{attribute}' attribute")

    @staticmethod
    def _build_approved_days(time_off_data):
        """Build a sorted list of all approved days from time-off requests."""
        days = set()
        for time_off in time_off_data:
            if not hasattr(time_off, 'status'):
                raise InvalidStateError("Time off object is missing 'status' attribute")
            
            if time_off.status != 'Approved':
                continue

            try:
                start = date.fromisoformat(time_off.start_date)
                end = date.fromisoformat(time_off.end_date)
                day = start
                while day <= end:
                    days.add(day.isoformat())
                    day += timedelta(days=1)
            except Exception as e:
                raise InvalidStateError(f"Invalid time off date format: {e}")
        return sorted(days)

    @staticmethod
    def split_background_event(event):
        """Split multi-day background events into calendar-compatible segments."""
        try:
            first_day_end = (date.fromisoformat(event['start']) + timedelta(days=1)).isoformat()
            first_day = {**event, 'end': first_day_end}
            if first_day_end >= event['end']:
                return [first_day]
            return [first_day, {**event, 'start': first_day_end, 'title': ''}]
        except (ValueError, KeyError) as e:
            raise InvalidStateError(f"Invalid event format: {e}")

    # ==========================================
    # API Helper Methods
    # ==========================================

    def get_weekly_grid(self, employee_id):
        """Get weekly availability grid for an employee.
        Returns list of dicts: {workday_id, shift_id, available}"""
        if self.employee_service.get_employee(employee_id) is None:
            raise NotFoundError(f"Employee {employee_id} not found")

        availabilities = []

        try:
            shifts = self.availability_repository.get_active_shifts()
            workdays = self.availability_repository.get_active_workdays()
        except sqlite3.Error as e:
            self._convert_db_error(e, "retrieving shifts and workdays")

        for shift in shifts:
            for workday_id in workdays:
                try:
                    avail = self.availability_repository.get_matching_availability(employee_id, workday_id, shift.shift_id)
                except sqlite3.Error as e:
                    self._convert_db_error(e, "retrieving matching availability")
                    
                if avail is None:
                    try:
                        cursor = self.availability_repository.conn.cursor()
                        avail = self.availability_repository.create_availability(
                            employee_id, shift.shift_id, workday_id, 2, cursor
                        )
                        self.availability_repository.commit()
                        availabilities.append(avail)
                    except sqlite3.Error as e:
                        self.availability_repository.rollback()
                        self._convert_db_error(e, "creating default availability entry")
                else:
                    availabilities.append(avail)

        return availabilities

    def replace_weekly_grid(self, employee_id, weekly_grid):
        """Replace entire availability grid for an employee.
        Each entry: {workday_id (1-7), shift_id, availability (0=Not available, 1=Available, 2=Unset)}"""
        if self.employee_service.get_employee(employee_id) is None:
            raise NotFoundError(f"Employee {employee_id} not found")
        
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

        try:
            return self.availability_repository.replace_weekly_grid(employee_id, weekly_grid)
        except sqlite3.Error as e:
            self._convert_db_error(e, "replacing weekly grid")

    def get_selectable_employees(self, current_user):
        """Get list of employees accessible to current user."""
        if current_user is None:
            raise PermissionDeniedError("User must be signed in")

        if current_user.system_role_id not in [2, 3]:
            raise PermissionDeniedError("Only managers and administrators can select employees")
        
        employees = self.employee_service.list_employees()

        if not employees:
            raise NotFoundError("No employees found")

        selectable_employees = [
            employee for employee in employees
            if self.user_can_access_employee(current_user, employee)
        ]
        return selectable_employees

    def user_can_access_employee(self, current_user, employee, inclusive=True):
        """Check if the current user has access to the specified employee."""
        if current_user.system_role_id not in [1, 2, 3]:
            raise PermissionDeniedError("User must be Employee, Manager, or Administrator")
        if current_user.employee_id == employee.employee_id:
            return inclusive
        if current_user.system_role_id == 1 and current_user.employee_id != employee.employee_id:
            return False
        if current_user.system_role_id == 2 and \
            self.employee_service.get_system_role(employee.employee_id) > 1:
            return False
        return True

    def update_availability(self, data, employee_id):
        """Update availability row to match new data provided by the user."""
        if not isinstance(data, dict):
            raise ValidationError([{"field": "body", "issue": "Request body must be a JSON object"}])

        availability = data.get("availability")
        self._validate_availability_value(availability)
        
        shift_name = data.get("shift_name")
        self._validate_shift_name(shift_name)
        
        start, end, start_time, end_time = self._extract_shift_times(data)

        try:
            shift = self.availability_repository.get_shift(shift_name, start_time, end_time)
        except sqlite3.Error as e:
            self._convert_db_error(e, "retrieving shift")
            
        if shift is None:
            raise NotFoundError("Shift not found")
        
        shift_id = shift.shift_id
        workday_id = start.isoweekday()
        
        employee_availability_id = self._validate_employee_availability_id(data.get("id"))
        if employee_availability_id is None:
            return self.create_availability(employee_id, shift_id, workday_id, availability)

        try:
            availability_obj = self.availability_repository.get_availability_by_id(employee_availability_id)
        except sqlite3.Error as e:
            self._convert_db_error(e, "retrieving availability by ID")
            
        if not self._validate_existing_availability(availability_obj, employee_id, shift_id, workday_id):
            return None

        try:
            self.availability_repository.update_availability(employee_availability_id, availability)
            return employee_availability_id
        except sqlite3.Error as e:
            self.availability_repository.rollback()
            self._convert_db_error(e, "updating availability")

    def create_availability(self, employee_id, shift_id, workday_id, availability):
        """Create a new availability entry."""
        try:
            existing = self.availability_repository.get_matching_availability(
                employee_id, workday_id, shift_id
            )
        except sqlite3.Error as e:
            self._convert_db_error(e, "retrieving matching availability")

        if existing is not None:
            try:
                self.availability_repository.update_availability(
                    existing.employee_availability_id, availability
                )
            except sqlite3.Error as e:
                self._convert_db_error(e, "updating existing availability")
            return existing.employee_availability_id

        try:
            cursor = self.availability_repository.conn.cursor()
            availability_obj = self.availability_repository.create_availability(
                employee_id, shift_id, workday_id, availability, cursor
            )
            self.availability_repository.commit()
            return availability_obj.employee_availability_id
        except sqlite3.Error as e:
            self.availability_repository.rollback()
            self._convert_db_error(e, "creating availability entry")

    def get_available_employees_for_shift(self, workday_id, shift_id):
        """Get list of available employees for a specific workday and shift."""
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

    def get_time_off_by_employee(self, employee_id):
        """Get all time-off requests for an employee."""
        if employee_id is None:
            raise ValidationError([{"field": "employee_id", "issue": "is required"}])
        if type(employee_id) is not int:
            raise ValidationError([{"field": "employee_id", "issue": "must be valid"}])
        try:
            time_off_objects = self.availability_repository.get_time_off_by_employee(employee_id)
        except sqlite3.Error as e:
            self._convert_db_error(e, "retrieving time-off requests for employee")
            
        if not time_off_objects:
            return []
        return time_off_objects

    def get_allowed_time_off_requests(self, current_user):
        """Get time-off requests that current user is allowed to access."""
        time_off_objs = []
        for employee in self.employee_service.list_employees():
            if self.user_can_access_employee(current_user, employee):
                time_off_objs.extend(self.get_time_off_by_employee(employee.employee_id))
        return time_off_objs

    def submit_time_off(self, data):
        """Create a new time-off request from the provided data."""
        employee_id = current_user.employee_id
        
        self._validate_employee_exists(employee_id)
        self._validate_time_off_dates_exist(data)
        
        start, end = self._extract_time_off_dates(data)
        self._validate_time_off_date_range(start, end)

        try:
            if self.availability_repository.check_time_off_overlap(employee_id, start, end):
                raise ConflictError("Dates overlap an existing time-off request")
        except sqlite3.Error as e:
            self.availability_repository.rollback()
            self._convert_db_error(e, "checking time-off overlap")

        try:
            time_off = self.availability_repository.create_time_off_request(
                employee_id, start, end
            )
        except sqlite3.Error as e:
            self.availability_repository.rollback()
            self._convert_db_error(e, "creating time-off request")

        return self._time_off_event(time_off)

    def availability_db_to_events(self, employee_availability_data, time_off_data, employee_id):
        """Convert availability and time-off data into calendar event formats."""
        formatted_data = []
        
        formatted_data.extend(self._build_unset_availability_events(employee_id))
        formatted_data.extend(self._build_saved_availability_events(employee_availability_data))
        
        background_data = self._build_time_off_background_events(time_off_data)
        
        return formatted_data, background_data, self._build_approved_days(time_off_data)

    def list_available(self, date, shift_id):
        """Get list of employees available for a specific date and shift."""
        workday_id = date.isoweekday()
        try:
            all_availabilities = self.availability_repository.get_availability_data()
        except sqlite3.Error as e:
            self._convert_db_error(e, "retrieving availability data for shift")
        
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
        """Update time-off request status (Approved, Denied, Cancelled)."""
        if status not in ("Approved", "Denied", "Cancelled"):
            raise ValidationError([{"field": "status", "issue": "status must be 'Approved', 'Denied', or 'Cancelled'"}])
        
        try:
            time_off = self.availability_repository.get_time_off_request(request_id)
            if time_off is None:
                raise NotFoundError(f"Time-off request {request_id} not found")
            
            if time_off.status != "Pending":
                raise ConflictError(f"Request is {time_off.status}, not Pending")
            
            success = self.availability_repository.update_time_off_request_by_id(request_id, status)
            if not success:
                raise ConflictError("Could not update request status")
            return self.availability_repository.get_time_off_request(request_id)
        except (NotFoundError, ConflictError, ValidationError):
            raise
        except sqlite3.Error as e:
            self.availability_repository.rollback()
            self._convert_db_error(e, "updating time-off request status")

    # ==========================================
    # Availability Data Retrieval
    # ==========================================

    def get_availability(self):
        """Get all availability records."""
        try:
            return self.availability_repository.get_availability_data()
        except sqlite3.Error as e:
            self._convert_db_error(e, "retrieving all availability records")

    def get_availability_by_employee(self, employee_id):
        """Get availability records for a specific employee."""
        try:
            return self.availability_repository.get_availability_by_employee(employee_id)
        except sqlite3.Error as e:
            self.availability_repository.rollback()
            self._convert_db_error(e, "retrieving employee availabilities")

    def get_time_off_request(self, request_id):
        """Get a specific time-off request by ID."""
        try:
            return self.availability_repository.get_time_off_request(request_id)
        except sqlite3.Error as e:
            self._convert_db_error(e, "retrieving time-off request")

    def is_employee_available(self, employee_id, workday_id, shift_id):
        """Check if employee is available for a specific workday and shift."""
        try:
            availability_obj = self.availability_repository.get_matching_availability(employee_id, workday_id, shift_id)
        except sqlite3.Error as e:
            self._convert_db_error(e, "retrieving availability for employee")
            
        if availability_obj is None:
            return False
        if availability_obj.availability is None:
            raise InvalidStateError("Availability is not set for this shift")
        return availability_obj.availability == 1

    # ==========================================
    # Calendar Event Building Helpers
    # ==========================================

    def _build_unset_availability_events(self, employee_id):
        """Build calendar events for shifts without saved availability."""
        events = []
        try:
            shifts = self.availability_repository.get_active_shifts()
            workdays = self.availability_repository.get_active_workdays()
        except sqlite3.Error as e:
            self._convert_db_error(e, "retrieving shifts and workdays for unset availability events")
            
        for shift in shifts:
            for workday_id in workdays:
                try:
                    avail = self.availability_repository.get_matching_availability(employee_id, workday_id, shift.shift_id)
                except sqlite3.Error as e:
                    self._convert_db_error(e, "retrieving matching availability for event building")
                    
                if avail is None:
                    events.append({
                        'id': None,
                        'title': shift.shift_name,
                        'startTime': self._as_calendar_time(shift.start_time),
                        'endTime': self._as_calendar_time(shift.end_time),
                        'daysOfWeek': [0 if workday_id == 7 else workday_id],
                        'availability': 2,
                        'color': 'gray',
                    })
        return events

    def _build_saved_availability_events(self, employee_availability_data):
        """Build calendar events from saved availability records."""
        events = []
        for item in employee_availability_data:
            try:
                shift_name = self.availability_repository.get_shift_name(item.shift_id)
                shift_start_time = self.availability_repository.get_shift_start_time(item.shift_id)
                shift_end_time = self.availability_repository.get_shift_end_time(item.shift_id)
            except sqlite3.Error as e:
                self._convert_db_error(e, "retrieving shift details for event building")
                
            events.append({
                'id': item.employee_availability_id,
                'title': shift_name,
                'startTime': self._as_calendar_time(shift_start_time),
                'endTime': self._as_calendar_time(shift_end_time),
                'daysOfWeek': [0 if item.workday_id == 7 else item.workday_id],
                'availability': item.availability,
                'color': 'green' if item.availability == 1 else 'gray' if item.availability == 2 else 'red',
            })
        return events

    def _build_time_off_background_events(self, time_off_data):
        """Build background events from time-off requests."""
        events = []
        for time_off in time_off_data:
            if time_off.status == 'Cancelled' or time_off.status == 'Viewed':
                continue
            events.append(self._time_off_event(time_off))
        return events

    # ==========================================
    # Availability Update Validation Helpers
    # ==========================================

    def _validate_availability_value(self, availability):
        """Validate availability value is 0, 1, or 2."""
        if type(availability) is not int or availability not in (0, 1, 2):
            raise ValidationError([{"field": "availability", "issue": "Availability must be 0, 1, or 2"}])

    def _validate_shift_name(self, shift_name):
        """Validate shift name is a non-empty string."""
        if not isinstance(shift_name, str) or not shift_name.strip():
            raise ValidationError([{"field": "shift_name", "issue": "Shift name is required"}])

    def _extract_shift_times(self, data):
        """Extract and validate start and end times from request data."""
        start = self._local_event_datetime(data, "start")
        end = self._local_event_datetime(data, "end")
        start_time = self._format_shift_time(start.replace(tzinfo=None).isoformat())
        end_time = self._format_shift_time(end.replace(tzinfo=None).isoformat())
        return start, end, start_time, end_time

    def _validate_employee_availability_id(self, employee_availability_id):
        """Validate and convert employee availability ID to integer."""
        if employee_availability_id in (None, "", "null", "None"):
            return None
        
        if not isinstance(employee_availability_id, int):
            try:
                employee_availability_id = int(employee_availability_id)
            except (TypeError, ValueError):
                raise ValidationError([{"field": "id", "issue": "Availability ID must be a positive integer"}])
        
        if employee_availability_id <= 0:
            raise ValidationError([{"field": "id", "issue": "Availability ID must be a positive integer"}])
        
        return employee_availability_id

    def _validate_existing_availability(self, availability_obj, employee_id, shift_id, workday_id):
        """Validate that existing availability record matches expected values."""
        if (availability_obj is None or availability_obj.employee_id != employee_id
                or availability_obj.shift_id != shift_id or availability_obj.workday_id != workday_id):
            return False
        return True

    # ==========================================
    # Time-Off Submission Validation Helpers
    # ==========================================

    def _validate_employee_exists(self, employee_id):
        """Validate that employee ID is valid and employee exists."""
        if employee_id is None:
            raise ValidationError([{"field": "employee_id", "issue": "is required"}])
        if type(employee_id) is not int:
            raise ValidationError([{"field": "employee_id", "issue": "must be valid"}])
        employee = self.employee_service.get_employee(employee_id)
        if employee is None:
            raise ValidationError([{"field": "employee_id", "issue": "must be valid"}])
        return employee

    def _validate_time_off_dates_exist(self, data):
        """Validate that start_date and end_date fields exist in request."""
        if "start_date" not in data:
            raise ValidationError([{"field": "start_date", "issue": "is required"}])
        if "end_date" not in data:
            raise ValidationError([{"field": "end_date", "issue": "is required"}])

    def _parse_time_off_date(self, value, field):
        """Parse and validate a date string in YYYY-MM-DD format."""
        if value is None:
            raise ValidationError([{"field": field, "issue": "is required"}])
        if not isinstance(value, str):
            raise ValidationError([{"field": field, "issue": "must be a date in YYYY-MM-DD format"}])
        
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError([{"field": field, "issue": "must be a date in YYYY-MM-DD format"}])

    def _extract_time_off_dates(self, data):
        """Extract and parse start and end dates from request data."""
        dates = []
        for field in ("start_date", "end_date"):
            value = data.get(field)
            dates.append(self._parse_time_off_date(value, field))
        return dates[0], dates[1]

    def _validate_time_off_date_range(self, start, end):
        """Validate start and end dates are valid and not in the past."""
        today = date.today()
        
        if start < today:
            raise ValidationError([{"field": "start_date", "issue": "must be today or later"}])
        if end < today:
            raise ValidationError([{"field": "end_date", "issue": "must be today or later"}])
        if end < start:
            raise ValidationError([{"field": "end_date", "issue": "must be on or after start_date"}])
        if end >= date.max:
            raise ValidationError([{"field": "end_date", "issue": "is too far in the future"}])
