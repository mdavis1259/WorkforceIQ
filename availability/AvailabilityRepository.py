"""
Availability Repository

Per the WorkforceIQ SDS, repositories own all
database access and SQL for their module.

Availability owns:

    - Availability
    - Shifts
"""
class AvailabilityRepository:
    def __init__(self, conn):
        self.conn = conn

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


    # Fetches all availability data for all employees, including shift details
    def get_availability(self):
        cursor = self.conn.cursor()

        cursor.execute(
                    """
                    SELECT ea.*, s.shift_name, s.start_time, s.end_time
                    FROM EmployeeAvailability AS ea
                    JOIN Shifts AS s ON s.shift_id = ea.shift_id
                    ORDER BY ea.employee_availability_id
                    """)

        return cursor.fetchall()

    # Fetches availability data for a specific user, including shift details
    def get_employee_availability(self, employee_id):
        cursor = self.conn.cursor()

        # Get: EmpAvailID, EmpID, Availability, ShiftName, StartTime, EndTime
        cursor.execute(
                    """ 
                    SELECT ea.*, s.shift_name, s.start_time, s.end_time
                    FROM EmployeeAvailability AS ea
                    JOIN Shifts AS s ON s.shift_id = ea.shift_id
                    WHERE ea.employee_id = ?
                    """,
                    (employee_id,)
        )

        return cursor.fetchall()

    def get_shift(self, shift_name, start_time, end_time):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM Shifts WHERE shift_name = ? AND start_time = ? AND end_time = ?",
            (shift_name, start_time, end_time)
        )
        return cursor.fetchone()

    def create_shift(self, shift_name, start_time, end_time):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO Shifts (shift_name, start_time, end_time) VALUES (?, ?, ?)",
            (shift_name, start_time, end_time)
        )
        return cursor.lastrowid

    def create_availability(self, employee_id, shift_id, availability):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO EmployeeAvailability (employee_id, shift_id, availability) VALUES (?, ?, ?)",
            (employee_id, shift_id, availability)
        )
        return cursor.lastrowid

    def get_shift_by_availability_id(self, employee_availability_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT shift_id "
            "FROM EmployeeAvailability "
            "WHERE employee_availability_id = ?",
            (employee_availability_id,)
        )
        return cursor.fetchone()

    # Deletes an availability entry and its corresponding shift for an employee, including shift details
    def delete_availability(self, data):
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object")

        employee_availability_id = data.get('id')
        if employee_availability_id is None:
            raise ValueError("AvailabilityID is required")

        cursor = self.conn.cursor()
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

        self.conn.commit()
        return True

    def update_shift(self, shift_id, shift_updates):
        if not shift_updates:
            return
        assignments = ', '.join(f"{column} = ?" for column in shift_updates)
        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE Shifts SET {assignments} WHERE shift_id = ?",
            (*shift_updates.values(), shift_id)
        )
        self.conn.commit()

    def update_availability(self, employee_availability_id, availability):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE EmployeeAvailability SET availability = ? WHERE employee_availability_id = ?",
            (availability, employee_availability_id)
        )
        self.conn.commit()

    # TODO: implement
    def is_employee_available(self, employee_id, schedule_date, shift_id):
        return True