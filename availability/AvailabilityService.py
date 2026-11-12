from calendar import monthrange
from datetime import date, datetime, timedelta


def availabilityDBtoEvents(availability_tuples):
    formatted_data = []
    for item in availability_tuples:
        formatted_dict = {
            'id': item['employee_availability_id'],
            'title': item['shift_name'],
            'start': item['start_time'],
            'end': item['end_time'],
            'color': 'red' if item['availability'] == 0 else 'green',
        }
        formatted_data.append(formatted_dict)
    return formatted_data


def build_availability_occurrences(data):
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