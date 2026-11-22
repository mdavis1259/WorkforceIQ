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

    # ==========================================
    # AVAILABILITY
    # ==========================================

    # Fetches all availability data for all employees, including shift details
    def get_availability_data(self):
        cursor = self.conn.cursor()

        cursor.execute(
                    """
                    SELECT ea.*, s.shift_name, s.start_time, s.end_time
                    FROM EmployeeAvailability AS ea
                    JOIN Shifts AS s ON s.shift_id = ea.shift_id
                    ORDER BY ea.employee_availability_id
                    """)

        return cursor.fetchall()

    def get_availability_by_id(self, employee_availability_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * "
            "FROM EmployeeAvailability "
            "WHERE employee_availability_id = ?",
            (employee_availability_id,)
        )
        return cursor.fetchone()

    def get_matching_availability(self, employee_id, workday_id, shift_id):
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM EmployeeAvailability WHERE employee_id = ? AND workday_id = ? AND shift_id = ?",
                (employee_id, workday_id, shift_id)
            )
            return cursor.fetchone()

    # Fetches availability data for a specific user, including shift details
    def get_availability_by_employee(self, employee_id):
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

    def create_availability(self, employee_id, shift_id, workday_id, availability):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO EmployeeAvailability (employee_id, shift_id, workday_id, availability) VALUES (?, ?, ?, ?)",
            (employee_id, shift_id, workday_id, availability)
        )
        self.conn.commit()
        return cursor.lastrowid

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
            "SELECT 1 FROM EmployeeAvailability WHERE shift_id = ? LIMIT 1",
            (shift_id,)
        )
        if cursor.fetchone() is None:
            cursor.execute(
                "DELETE FROM Shifts WHERE shift_id = ?",
                (shift_id,)
            )

        self.conn.commit()
        return True

    def update_availability(self, employee_availability_id, availability):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE EmployeeAvailability SET availability = ? WHERE employee_availability_id = ?",
            (availability, employee_availability_id)
        )
        self.conn.commit()

    # ==========================================
    # SHIFTS
    # ==========================================

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

    def get_active_shifts(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM Shifts WHERE active = 1"
        )
        return cursor.fetchall()

    def get_shift_name(self, shift_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT shift_name FROM Shifts WHERE shift_id = ?",
            (shift_id,)
        )
        row = cursor.fetchone()
        return row['shift_name'] if row else None
    
    def get_shift_start_time(self, shift_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT start_time FROM Shifts WHERE shift_id = ?",
            (shift_id,)
        )
        row = cursor.fetchone()
        return row['start_time'] if row else None
    
    def get_shift_end_time(self, shift_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT end_time FROM Shifts WHERE shift_id = ?",
            (shift_id,)
        )
        row = cursor.fetchone()
        return row['end_time'] if row else None

    # ==========================================
    # WORKDAYS
    # ==========================================

    def get_active_workdays(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM Workdays WHERE active = 1"
        )
        return [row['workday_id'] for row in cursor.fetchall()]

        # Returns the days of the week where an employee's availability per shift is the same  
    def get_days_with_matching_availability(self, employee_availability_id, shift_id, availability):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT ea.workday_id
            FROM EmployeeAvailability AS ea
            JOIN EmployeeAvailability AS selected
              ON selected.employee_id = ea.employee_id
            WHERE selected.employee_availability_id = ?
              AND ea.shift_id = ?
              AND ea.availability = ?
            ORDER BY ea.workday_id
            """,
            (employee_availability_id, shift_id, availability)
        )
        days = cursor.fetchall()

        # Extract the workday_id values from the query result
        daystring = ", ".join(
            str(0 if day["workday_id"] == 7 else day["workday_id"])
            for day in days
        )

        return daystring

    # ==========================================
    # TIME OFF
    # ==========================================

    def get_time_off_by_employee(self, employee_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM TimeOffRequests WHERE employee_id = ?",
            (employee_id,)
        )
        return cursor.fetchall()