"""
Scheduling Repository

Per the WorkforceIQ SDS, repositories own all
database access and SQL for their module.

Scheduling owns:

    - Shifts
    - Staffing Requirements
"""

class SchedulingRepository:

    def __init__(self, conn):
        self.conn = conn

    # ==========================================
    # SHIFTS
    # ==========================================

    def get_shifts(self):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Shifts
            ORDER BY start_time
        """)

        return cursor.fetchall()

    def get_shift_by_id(self, shift_id):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Shifts
            WHERE shift_id = ?
        """, (shift_id,))

        return cursor.fetchone()

    def create_shift(
        self,
        shift_name,
        start_time,
        end_time
    ):

        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO Shifts (
                shift_name,
                start_time,
                end_time
            )
            VALUES (?, ?, ?)
        """, (
            shift_name,
            start_time,
            end_time
        ))

        self.conn.commit()

        return self.get_shift_by_id(cursor.lastrowid)

    def update_shift(
        self,
        shift_id,
        shift_name,
        start_time,
        end_time
    ):

        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE Shifts
            SET
                shift_name = ?,
                start_time = ?,
                end_time = ?
            WHERE shift_id = ?
        """, (
            shift_name,
            start_time,
            end_time,
            shift_id
        ))

        self.conn.commit()

        return self.get_shift_by_id(shift_id)

    def delete_shift(self, shift_id):

        cursor = self.conn.cursor()

        cursor.execute("""
            DELETE
            FROM Shifts
            WHERE shift_id = ?
        """, (shift_id,))

        self.conn.commit()

    # ===============================================
    # STAFFING REQUIREMENTS
    # ===============================================

    def get_staffing_requirements(self):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                sr.shift_id,
                sr.role_id,
                s.shift_name,
                GROUP_CONCAT(
                    DISTINCT wd.day_name
                ) AS workdays,
                r.role_name,
                sr.required_count
            FROM StaffingRequirements sr
            JOIN Workdays wd
                ON sr.workday_id = wd.workday_id
            JOIN Shifts s
                ON sr.shift_id = s.shift_id
            JOIN Roles r
                ON sr.role_id = r.role_id
            GROUP BY
                sr.shift_id,
                sr.role_id,
                sr.required_count
            ORDER BY
                s.start_time,
                r.role_name
        """)

        return cursor.fetchall()

    def get_staffing_requirement_by_id(
        self,
        requirement_id
    ):
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM StaffingRequirements
            WHERE requirement_id = ?
        """, ( requirement_id,))

        return cursor.fetchone()

    def staffing_requirement_exists(self, workday_id, shift_id, role_id):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM StaffingRequirements
            WHERE workday_id = ?
            AND shift_id = ?
            AND role_id = ?       
        """, (workday_id, shift_id, role_id))

        return cursor.fetchone() is not None
    

    def create_staffing_requirement(
        self,
        workday_id,
        shift_id,
        role_id,
        required_count
    ):

        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO StaffingRequirements(
                workday_id,
                shift_id,
                role_id,
                required_count
            )
            VALUES (?, ?, ?, ?)
        """, (
            workday_id,
            shift_id,
            role_id,
            required_count
        ))

        self.conn.commit()

        return self.get_staffing_requirement_by_id(cursor.lastrowid)

    def update_staffing_requirement(
        self,
        shift_id,
        role_id,
        required_count
    ):

        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE StaffingRequirements
            SET required_count = ?
            WHERE shift_id = ?
            AND role_id = ?
        """, (
            required_count,
            shift_id,
            role_id
        ))

        self.conn.commit()

    def delete_staffing_requirement(self, shift_id, role_id):

        cursor = self.conn.cursor()

        cursor.execute("""
            DELETE
            FROM StaffingRequirements
            WHERE shift_id = ?
            AND role_id = ?
        """, (shift_id, role_id))

        self.conn.commit()

    # =========================================================
    # WORKDAYS
    # =========================================================
    def get_workdays(self):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Workdays
            ORDER BY Workday_id
        """)

        return cursor.fetchall()

    def get_workday_by_id(self, workday_id):
    
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Workdays
            WHERE workday_id = ?
        """, (workday_id,))

        return cursor.fetchone()

    def update_workday(self, workday_id, active):

        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE Workdays
            SET active = ?
            WHERE workday_id = ?
        """, (int(active), workday_id))

        self.conn.commit()

        return self.get_workday_by_id(workday_id)

    # =====================================================
    # SCHEDULES
    # =====================================================
    def create_schedule(self, week_start, status="Draft"):
        
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO Schedules(
                week_start,
                status
            )
            VALUES (?, ?)
        """, (
            week_start,
            status
        ))

        self.conn.commit()

        return self.get_schedule_by_id(cursor.lastrowid)

    def get_schedule_by_id(self, schedule_id):
        
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Schedules
            WHERE schedule_id = ?
        """, (schedule_id,))

        return cursor.fetchone()

    def get_schedule_by_week(self, week_start):
        
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Schedules
            WHERE week_start = ?
        """, (week_start,))

        return cursor.fetchone()

    # ===============================================
    # ASSIGNMENTS
    # ===============================================
    
    def create_assignment(
        self,
        schedule_id,
        employee_id,
        role_id,
        shift_id,
        schedule_date,
        hours
    ):
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO ShiftAssignments(
                schedule_id,
                employee_id,
                role_id,
                shift_id,
                schedule_date,
                hours
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            schedule_id,
            employee_id,
            role_id,
            shift_id,
            schedule_date,
            hours
        ))

        self.conn.commit()

    def get_assignments(self, schedule_id):
        
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                sa.*,
                e.first_name,
                e.last_name,
                s.shift_name
            FROM ShiftAssignments sa
            JOIN Employees e
                ON sa.employee_id = e.employee_id
            JOIN Shifts s
                ON sa.shift_id = s.shift_id
            WHERE sa.schedule_id = ?
            ORDER BY sa.schedule_date
        """, (schedule_id,))

        return cursor.fetchall()
    
    def get_staffing_requirement_rows(self):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                sr.workday_id,
                wd.day_name,

                sr.shift_id,
                s.shift_name,

                sr.role_id,
                r.role_name,

                sr.required_count

            FROM StaffingRequirements sr

            JOIN Workdays wd
                ON sr.workday_id = wd.workday_id

            JOIN Shifts s
                ON sr.shift_id = s.shift_id

            JOIN Roles r
                ON sr.role_id = r.role_id

            ORDER BY 
                sr.workday_id,
                s.start_time,
                r.role_name
        """)

        rows = cursor.fetchall()

        if rows:
            print(dict(rows[0]))

        return rows

    # ======================================
    # EMPLOYEES
    # ======================================

    def get_employees_by_role(self, role_id):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Employees
            WHERE role_id = ?
            AND active = 1
        """, (role_id,))

        return cursor.fetchall()

    def get_employee_hours_for_week(self, employee_id, week_start):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT COALESCE(SUM(hours), 0)
            FROM ShiftAssignments
            WHERE employee_id = ?
                AND schedule_date >= ?
                AND schedule_date <= date(?, '+7 days')
        """, (employee_id, week_start, week_start))

        return cursor.fetchone()[0]

    def get_employee_assignments_for_date(self, employee_id, schedule_date):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT sa.*,
                   s.start_time,
                   s.end_time
            FROM ShiftAssignments sa
            JOIN Shifts s
                ON s.shift_id = sa.shift_id
            WHERE sa.employee_id = ?
            AND sa.schedule_date = ?
        """, (employee_id, schedule_date))

        return cursor.fetchall()

    def has_overlapping_assignment(self, employee_id, schedule_date, shift_id):

        cursor = self.conn.cursor()

        # Candidate shift
        cursor.execute("""
            SELECT start_time, end_time
            FROM Shifts
            WHERE shift_id = ?
        """, (shift_id,))

        candidate_shift = cursor.fetchone()

        if candidate_shift is None:
            return False

        candidate_start = candidate_shift["start_time"]
        candidate_end = candidate_shift["end_time"]

        # Existing assignments for same employee/date
        cursor.execute("""
            SELECT
                s.start_time,
                s.end_time
            FROM ShiftAssignments sa
            JOIN Shifts s
                ON s.shift_id = sa.shift_id
            WHERE sa.employee_id = ?
            AND sa.schedule_date = ?
        """, (employee_id, schedule_date))

        assignments = cursor.fetchall()

        for assignment in assignments:
            existing_start = assignment["start_time"]
            existing_end = assignment["end_time"]

            if (candidate_start < existing_end and candidate_end > existing_start):
                return True
        
        return False
