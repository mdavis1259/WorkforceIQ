from datetime import datetime

from database.connection import get_db_connection

# Fetches all availability data for all employees, including shift details
def get_availability():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
                   """
                   SELECT ea.*, s.shift_name, s.start_time, s.end_time, s.active
                   FROM EmployeeAvailability AS ea
                   JOIN Shifts AS s ON s.shift_id = ea.shift_id
                   """)
    returned_data = cursor.fetchall()
    conn.close()

    return returned_data

# Fetches availability data for a specific user, including shift details
def get_employee_availability(employee_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get: EmpAvailID, EmpID, Availability, ShiftName, StartTime, EndTime, Active
    cursor.execute(
                   """
                   SELECT ea.*, s.shift_name, s.start_time, s.end_time, s.active
                   FROM EmployeeAvailability AS ea
                   JOIN Shifts AS s ON s.shift_id = ea.shift_id
                   WHERE ea.employee_id = ?
                   """,
                   (employee_id,))
    returned_data = cursor.fetchall()
    conn.close()

    return returned_data

# Creates a new availability entry and corresponding shift for an employee, including shift details
def create_availability(employee_id, data):
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object")

    # Get the required fields from the data dictionary
    shift_name = data.get('title')
    start = data.get('start')
    end = data.get('end')
    availability = data.get('availability')

    # Validate the required fields
    if employee_id is None:
        raise ValueError("EmployeeID is required")
    if not isinstance(shift_name, str) or not shift_name.strip():
        raise ValueError("Title must be a non-empty string")
    if not isinstance(start, str) or not isinstance(end, str):
        raise ValueError("Start and end times are required")
    if availability not in (0, 1, False, True):
        raise ValueError("Availability must be False or True")

    # Validate the start and end times
    try:
        start_datetime = datetime.fromisoformat(start)
        end_datetime = datetime.fromisoformat(end)
    except ValueError as error:
        raise ValueError("Start and end times must be valid ISO date-times") from error
    if start_datetime.tzinfo != end_datetime.tzinfo:
        raise ValueError("Start and end times must use the same time zone")
    if end_datetime <= start_datetime:
        raise ValueError("End time must be after start time")

    # Add the availability entry to the database
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Check if the employee exists
        cursor.execute("SELECT employee_id FROM Employees WHERE employee_id = ?", (employee_id,))
        employee_row = cursor.fetchone()
        if employee_row is None:
            return None

        # Make new shift entry and get the shift_id if the Shift doesn't exist
        cursor.execute(
            "SELECT shift_id FROM Shifts WHERE shift_name = ? AND start_time = ? AND end_time = ?",
            (shift_name.strip(), start, end)
        )
        shift_row = cursor.fetchone()
        if shift_row:
            shift_id = shift_row['shift_id']
        else:
            cursor.execute(
                "INSERT INTO Shifts (shift_name, start_time, end_time) VALUES (?, ?, ?)",
                (shift_name.strip(), start, end)
            )
            shift_id = cursor.lastrowid

        # Make new availability entry
        cursor.execute(
            """
            INSERT INTO EmployeeAvailability (employee_id, shift_id, availability)
            VALUES (?, ?, ?)
            """,
            (employee_row['employee_id'], shift_id, int(availability))
        )

        # Get the employee_availability_id to set for event id in calendar
        availability_id = cursor.lastrowid
        conn.commit()
        return availability_id
    finally:
        conn.close()


def update_availability(data):
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

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT shift_id FROM EmployeeAvailability WHERE employee_availability_id = ?",
            (employee_availability_id,)
        )
        # Check availability entry exists
        availability_row = cursor.fetchone()
        if availability_row is None:
            return False

        #If shift details changed
        shift_id = availability_row['shift_id']
        if shift_updates:
            # Use string operations to only UPDATE the fields that changed
            assignments = ', '.join(f"{column} = ?" for column in shift_updates)
            cursor.execute(
                f"UPDATE Shifts SET {assignments} WHERE shift_id = ?",
                (*shift_updates.values(), shift_id)
            )

        # If availability changed
        if availability_update is not None:
            cursor.execute(
                """
                UPDATE EmployeeAvailability
                SET availability = ?
                WHERE employee_availability_id = ?
                """,
                (availability_update, employee_availability_id)
            )

        conn.commit()
        return True
    finally:
        conn.close()

# Deletes an availability entry and its corresponding shift for an employee, including shift details
def delete_availability(data):
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object")

    employee_availability_id = data.get('id')
    if employee_availability_id is None:
        raise ValueError("AvailabilityID is required")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT shift_id FROM EmployeeAvailability WHERE employee_availability_id = ?",
            (employee_availability_id,)
        )
        availability_row = cursor.fetchone()
        if availability_row is None:
            return False

        shift_id = availability_row['shift_id']
        cursor.execute(
            "DELETE FROM EmployeeAvailability WHERE employee_availability_id = ?",
            (employee_availability_id,)
        )
        cursor.execute(
            "DELETE FROM Shifts WHERE shift_id = ?",
            (shift_id,)
        )

        conn.commit()
        return True
    finally:
        conn.close()