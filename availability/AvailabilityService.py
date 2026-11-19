from calendar import monthrange
from datetime import date, datetime, timedelta

from errors import NotFoundError
from shared.exceptions import ValidationError

class AvailabilityService:
    def __init__(self, availability_repository, employee_service):
        self.availability_repository = availability_repository
        self.employee_service = employee_service

    def get_availability(self):
        return self.availability_repository.get_availability()

    def get_employee_availability(self, employee_id):
        return self.availability_repository.get_employee_availability(employee_id)
    
    def list_employees(self, associates_only=False):
        employees = self.employee_service.list_employees()

        if associates_only:
            employees = [
                employee for employee in employees
                if self.employee_service.get_system_role(employee.role_id) == 1
            ]
        return employees

    def availability_db_to_events(self, availability_tuples):
        formatted_data = []
        for item in availability_tuples:
            formatted_data.append({
                'id': item['employee_availability_id'],
                'title': item['shift_name'],
                'start': item['start_time'],
                'end': item['end_time'],
                'color': 'red' if item['availability'] == 0 else 'green',
            })
        return formatted_data


    def build_availability_occurrences(self, data):
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object")

        title = data.get("title")
        start = data.get("start")
        end = data.get("end")
        availability = data.get("availability")
        recurrence = data.get("recurrence", "none")

        if not isinstance(title, str) or not title.strip():
            raise ValueError("Title must be a non-empty string")
        if not isinstance(start, str) or not isinstance(end, str):
            raise ValueError("Start and end times are required")
        if availability not in (0, 1, False, True):
            raise ValueError("Availability must be False or True")

        try:
            start_datetime = datetime.fromisoformat(start)
            end_datetime = datetime.fromisoformat(end)
        except ValueError as error:
            raise ValueError("Start and end times must be valid ISO date-times") from error
        if start_datetime.tzinfo != end_datetime.tzinfo:
            raise ValueError("Start and end times must use the same time zone")
        if end_datetime <= start_datetime:
            raise ValueError("End time must be after start time")

        if recurrence == "none":
            recurrence_starts = [start_datetime]
        else:
            if recurrence not in ("weekly", "monthly"):
                raise ValueError("Recurrence must be none, weekly, or monthly")
            recurrence_until = data.get("recurrence_until")
            if not isinstance(recurrence_until, str):
                raise ValueError("A recurrence end date is required")
            try:
                until = date.fromisoformat(recurrence_until)
            except ValueError as error:
                raise ValueError("Recurrence end date must be a valid date") from error
            if until < start_datetime.date():
                raise ValueError("Recurrence end date must be on or after the event date")

            recurrence_starts = []
            occurrence_number = 0
            while True:
                if recurrence == "weekly":
                    occurrence = start_datetime + timedelta(weeks=occurrence_number)
                else:
                    month_index = start_datetime.month - 1 + occurrence_number
                    year = start_datetime.year + month_index // 12
                    month = month_index % 12 + 1
                    day = min(start_datetime.day, monthrange(year, month)[1])
                    occurrence = start_datetime.replace(year=year, month=month, day=day)

                if occurrence.date() > until:
                    break
                recurrence_starts.append(occurrence)
                occurrence_number += 1

        duration = end_datetime - start_datetime
        return [
            {
                "title": title.strip(),
                "start": occurrence.isoformat(),
                "end": (occurrence + duration).isoformat(),
                "availability": int(availability),
            }
            for occurrence in recurrence_starts
        ]

    def get_availability(self):
        return self.availability_repository.get_availability()

    def get_employee_availability(self, employee_id):
        return self.availability_repository.get_employee_availability(employee_id)
    
    def create_availability_series(self, employee_id, occurrences):
        if employee_id is None:
            raise ValidationError("EmployeeID is required")
        if not isinstance(occurrences, list) or not occurrences:
            raise ValidationError("At least one availability occurrence is required")

        try:
            self.employee_service.get_employee(employee_id)
        except NotFoundError:
            return None

        created_events = []
        try:
            for occurrence in occurrences:
                shift_name = occurrence["title"]
                start = occurrence["start"]
                end = occurrence["end"]
                shift_row = self.availability_repository.get_shift(shift_name, start, end)
                if shift_row:
                    shift_id = shift_row['shift_id']
                else:
                    shift_id = self.availability_repository.create_shift(shift_name, start, end)

                created_event_id = self.availability_repository.create_availability(employee_id, shift_id, occurrence["availability"])
                created_events.append({
                    "id": created_event_id,
                    "start": start,
                    "end": end,
                })
            self.availability_repository.commit()
        except BaseException:
            self.availability_repository.rollback()
            raise

        return created_events
    
    def update_availability(self, data):
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object")
        
        employee_availability_id = data.get('id')
        if employee_availability_id is None:
            raise ValueError("AvailabilityID is required")
        
        # Get the fields to update from the data dictionary, may not be all fields
        shift_updates = {}
        if 'start' in data:
            shift_updates['start_time'] = data['start']
        if 'end' in data:
            shift_updates['end_time'] = data['end']
        if 'title' in data:
            shift_name = data['title']
            if not isinstance(shift_name, str) or not shift_name.strip():
                raise ValueError("Title must be a non-empty string")
            shift_updates['shift_name'] = shift_name.strip()

        availability_update = None
        if 'availability' in data:
            availability = data['availability']
            if availability not in (0, 1, False, True):
                raise ValueError("Availability must be False or True")
            availability_update = int(availability)

        if not shift_updates and availability_update is None:
            raise ValueError("No availability changes provided")

        # Check availability entry exists
        availability_row = self.availability_repository.get_shift_by_availability_id(employee_availability_id)
        if availability_row is None:
            return False

        #If shift details changed
        shift_id = availability_row['shift_id']
        if shift_updates:
            # Use string operations to only UPDATE the fields that changed
            assignments = ', '.join(f"{column} = ?" for column in shift_updates)
            
            self.availability_repository.update_shift(shift_id, shift_updates)

        # If availability changed
        if availability_update is not None:
            self.availability_repository.update_availability(employee_availability_id, availability_update)

        return True
        
    def delete_availability(self, data):
        return self.availability_repository.delete_availability(data)

    def create_availability(self, employee_id, data):
        occurrences = self.build_availability_occurrences(data)
        created_events = self.create_availability_series(employee_id, occurrences)
        if not created_events:
            return None
        return created_events[0]["id"]

    def is_employee_available(self, employee_id, schedule_date, shift_id):
        return self.availability_repository.is_employee_available(employee_id, schedule_date, shift_id)
    