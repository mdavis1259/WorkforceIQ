"""
Availability Repository

Per the WorkforceIQ SDS, repositories own all
database access and SQL for their module.

Availability owns:

    - Availability
    - Shifts
    - TimeOff
"""
from sqlite3 import InternalError
import sqlite3

from availability.Availability import Availability
from availability.Shift import Shift
from availability.TimeOff import TimeOff
from errors import ConflictError, ValidationError


class AvailabilityRepository:
    def __init__(self, conn):
        self.conn = conn

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def row_to_availability(self, row):
        return Availability(
            employee_availability_id=row["employee_availability_id"],
            employee_id=row["employee_id"],
            shift_id=row["shift_id"],
            workday_id=row["workday_id"],
            availability=row["availability"]
        )

    def row_to_shift(self, row):
        return Shift(
            shift_id=row["shift_id"],
            shift_name=row["shift_name"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            active=row["active"] if "active" in row.keys() else None
        )

    def row_to_time_off(self, row):
        return TimeOff(
            request_id=row["request_id"],
            employee_id=row["employee_id"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            status=row["status"]
        )

    # ==========================================
    # AVAILABILITY
    # ==========================================

    # TODO: finish while allowing rollback in case of errors
    def replace_weekly_grid(self, employee_id, weekly_grid):
        # Clear existing
        try:
            current_employee_availabilities = self.get_availability_by_employee(employee_id)
        except sqlite3.Error as e:
            raise InternalError("Error retrieving employee availabilities") from e

        cursor = self.conn.cursor()
        try:
            for avail in current_employee_availabilities:
                try:
                    self.delete_availability({"id": avail.employee_availability_id})
                except sqlite3.Error as e:
                    self._convert_db_error(e, "deleting existing availability")
                    raise
            self.conn.commit()
        except sqlite3.Error as sql_err:
            self._convert_db_error(sql_err, "deleting existing availability")
            self.conn.rollback()
            raise

        new_availability_objects = []
        # Create new
        for entry in weekly_grid:
            # Do not add unset entries to repository
            if entry.get("availability") == 2:
                continue
            try:
                avail_obj = self.create_availability(
                    employee_id, entry["shift_id"], entry["workday_id"], entry["availability"]
                )
                new_availability_objects.append(avail_obj)
            except sqlite3.Error as e:
                self._convert_db_error(e, "creating new availability entry")
                raise

        return new_availability_objects

    # Fetches all availability data for all employees
    def get_availability_data(self):
        cursor = self.conn.cursor()

        cursor.execute(
                    """
                    SELECT ea.*, s.shift_name, s.start_time, s.end_time
                    FROM EmployeeAvailability AS ea
                    JOIN Shifts AS s ON s.shift_id = ea.shift_id
                    ORDER BY ea.employee_availability_id
                    """)

        rows = cursor.fetchall()
        return [self.row_to_availability(row) for row in rows]

    def get_availability_by_id(self, employee_availability_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * "
            "FROM EmployeeAvailability "
            "WHERE employee_availability_id = ?",
            (employee_availability_id,)
        )
        row = cursor.fetchone()
        return self.row_to_availability(row) if row else None

    def get_matching_availability(self, employee_id, workday_id, shift_id):
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM EmployeeAvailability WHERE employee_id = ? AND workday_id = ? AND shift_id = ?",
                (employee_id, workday_id, shift_id)
            )
            row = cursor.fetchone()
            return self.row_to_availability(row) if row else None

    # Fetches availability data for a specific employee
    def get_availability_by_employee(self, employee_id):
        cursor = self.conn.cursor()

        cursor.execute(
                    """ 
                    SELECT ea.*, s.shift_name, s.start_time, s.end_time
                    FROM EmployeeAvailability AS ea
                    JOIN Shifts AS s ON s.shift_id = ea.shift_id
                    WHERE ea.employee_id = ?
                    """,
                    (employee_id,)
        )

        rows = cursor.fetchall()
        return [self.row_to_availability(row) for row in rows]

    def create_availability(self, employee_id, shift_id, workday_id, availability):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO EmployeeAvailability (employee_id, shift_id, workday_id, availability) VALUES (?, ?, ?, ?)",
                (employee_id, shift_id, workday_id, availability)
            )
            availability_id = cursor.lastrowid
            if not availability_id:
                raise InternalError("Error creating availability")
            self.conn.commit()
            return Availability(
                employee_availability_id=availability_id,
                employee_id=employee_id,
                shift_id=shift_id,
                workday_id=workday_id,
                availability=availability
            )
        except InternalError:
            self.conn.rollback()
            raise

    # Deletes an availability entry and its corresponding shift for an employee
    def delete_availability(self, data, cursor):
        if data is None:
            raise ValidationError("Request body is required")
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object")

        employee_availability_id = data.get('id')
        if employee_availability_id is None:
            raise ValidationError("AvailabilityID is required")
        
        
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
        return True

    def update_availability(self, employee_availability_id, availability):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE EmployeeAvailability SET availability = ? WHERE employee_availability_id = ?",
                (availability, employee_availability_id)
            )
            self.conn.commit()
        except InternalError:
            self.conn.rollback()
            raise

    # ==========================================
    # SHIFTS
    # ==========================================

    def get_shift(self, shift_name, start_time, end_time):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM Shifts WHERE shift_name = ? AND start_time = ? AND end_time = ?",
            (shift_name, start_time, end_time)
        )
        row = cursor.fetchone()
        return self.row_to_shift(row) if row else None

    def create_shift(self, shift_name, start_time, end_time):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO Shifts (shift_name, start_time, end_time) VALUES (?, ?, ?)",
                (shift_name, start_time, end_time)
            )
            shift_id = cursor.lastrowid
            if not shift_id:
                raise InternalError("Error creating shift")
            self.conn.commit()
            return Shift(
                shift_id=shift_id,
                shift_name=shift_name,
                start_time=start_time,
                end_time=end_time
            )
        except InternalError:
            self.conn.rollback()
            raise

    def update_shift(self, shift_id, shift_updates):
        if not shift_updates:
            return
        assignments = ', '.join(f"{column} = ?" for column in shift_updates)
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                f"UPDATE Shifts SET {assignments} WHERE shift_id = ?",
                (*shift_updates.values(), shift_id)
            )
            self.conn.commit()
        except InternalError:
            self.conn.rollback()
            raise

    def get_active_shifts(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM Shifts WHERE active = 1"
        )
        rows = cursor.fetchall()
        return [self.row_to_shift(row) for row in rows]

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
        rows = cursor.fetchall()
        return [self.row_to_time_off(row) for row in rows]

    def get_all_time_off_requests(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM TimeOffRequests ORDER BY request_id")
        rows = cursor.fetchall()
        return [self.row_to_time_off(row) for row in rows]

    def get_time_off_request(self, request_id, employee_id):
        cursor = self.conn.execute(
            "SELECT * FROM TimeOffRequests WHERE request_id = ? AND employee_id = ?",
            (request_id, employee_id),
        )
        row = cursor.fetchone()
        return self.row_to_time_off(row) if row else None

    def create_time_off_request(self, employee_id, start_date, end_date):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO TimeOffRequests (employee_id, start_date, end_date, status) VALUES (?, ?, ?, 'Pending')",
                (employee_id, start_date, end_date)
            )
            request_id = cursor.lastrowid
            if not request_id:
                raise InternalError("Error creating time-off request")
            time_off_row = self.get_time_off_request_by_id(request_id)
            if not time_off_row:
                raise InternalError("Error retrieving created time-off request")
            self.conn.commit()
            return time_off_row
        except InternalError:
            self.conn.rollback()
            raise

    def update_pending_time_off(self, request_id, employee_id, status):
        try:
            cursor = self.conn.execute(
                "UPDATE TimeOffRequests SET status = ? "
                "WHERE request_id = ? AND employee_id = ? AND status = 'Pending'",
                (status, request_id, employee_id),
            )
            self.conn.commit()
            return cursor.rowcount == 1
        except InternalError:
            self.conn.rollback()
            raise

    def delete_availability_by_id(self, employee_availability_id):
        """Delete an availability entry by ID."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM EmployeeAvailability WHERE employee_availability_id = ?",
                (employee_availability_id,)
            )
            self.conn.commit()
            return cursor.rowcount == 1
        except InternalError:
            self.conn.rollback()
            raise

    def get_time_off_request_by_id(self, request_id):
        """Get a time-off request by ID (without employee_id filter)."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM TimeOffRequests WHERE request_id = ?", (request_id,))
        row = cursor.fetchone()
        return self.row_to_time_off(row) if row else None

    def update_time_off_request_by_id(self, request_id, status):
        """Update a time-off request status by ID."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE TimeOffRequests SET status = ? WHERE request_id = ? AND status = 'Pending'",
                (status, request_id)
            )
            self.conn.commit()
            return cursor.rowcount == 1
        except InternalError:
            self.conn.rollback()
            raise

    def check_time_off_overlap(self, employee_id, start_date, end_date):
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM TimeOffRequests
            WHERE employee_id = ?
            AND status IN ('Pending', 'Approved', 'Denied')
            AND start_date <= ? AND end_date >= ?
            """,
            (employee_id, end_date, start_date)
        )
        count = cursor.fetchone()[0]
        return count > 0