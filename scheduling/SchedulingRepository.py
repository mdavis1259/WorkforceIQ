"""
Scheduling Repository

Per the WorkforceIQ SDS, repositories own all
database access and SQL for their module.

Scheduling owns:

    - Schedules
    - Staffing Requirements
    - Shift Assignments
"""
from scheduling.Shift import (ShiftRequirement, ShiftAssignment, StaffingRequirement)
from scheduling.Schedule import Schedule

class SchedulingRepository:

    def __init__(self, conn):
        self.conn = conn

    # ===============================================
    # STAFFING REQUIREMENTS
    # ===============================================

    def get_staffing_requirements(self):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                sr.requirement_id,
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
        return [
            StaffingRequirement(
                workday_id=row["workday_id"],
                day_name=row["day_name"],
                shift_id=row["shift_id"],
                shift_name=row["shift_name"],
                role_id=row["role_id"],
                role_name=row["role_name"],
                required_count=row["required_count"]
            )
            for row in cursor.fetchall()
        ]

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

        row = cursor.fetchone()

        if row is None:
            return None

        return StaffingRequirement(
            workday_id=row["workday_id"],
            shift_id=row["shift_id"],
            role_id=row["role_id"],
            required_count=row["required_count"]
        )

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
        requirement_id,
        required_count
    ):

        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE StaffingRequirements
            SET required_count = ?
            WHERE requirement_id = ?
        """, (
            required_count,
            requirement_id
        ))

        self.conn.commit()

    def delete_staffing_requirement(self, requirement_id):

        cursor = self.conn.cursor()

        cursor.execute("""
            DELETE
            FROM StaffingRequirements
            WHERE requirement_id = ?
        """, (requirement_id,))

        self.conn.commit()

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

        row = cursor.fetchone()

        if row is None:
            return None

        return Schedule(
            schedule_id=row["schedule_id"],
            week_start=row["week_start"],
            status=row["status"]
        )

    def get_schedule_by_week(self, week_start):
        
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Schedules
            WHERE week_start = ?
        """, (week_start,))

        row = cursor.fetchone()

        if row is None:
            return None

        return Schedule(
            schedule_id=row["schedule_id"],
            week_start=row["week_start"],
            status=row["status"]
        )

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
                e.hourly_rate,
                s.shift_name
            FROM ShiftAssignments sa
            JOIN Employees e
                ON sa.employee_id = e.employee_id
            JOIN Shifts s
                ON sa.shift_id = s.shift_id
            WHERE sa.schedule_id = ?
            ORDER BY sa.schedule_date
        """, (schedule_id,))

        return [
            ShiftAssignment(
                assignment_id=row["assignment_id"],
                schedule_id=row["schedule_id"],
                employee_id=row["employee_id"],
                role_id=row["role_id"],
                shift_id=row["shift_id"],
                schedule_date=row["schedule_date"],
                employee_name=f"{row['first_name']} {row['last_name']}",
                role_name=row["role_name"] if "role_name" in row.keys() else "",
                hours=row["hours"]
            )
            for row in cursor.fetchall()
        ]
    

    def get_assignments_for_shift(self, schedule_id, shift_id, schedule_date):
        
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                sa.assignment_id,
                sa.employee_id,
                sa.role_id,
                e.first_name,
                e.last_name,
                r.role_name,
                sa.hours
            FROM ShiftAssignments sa
            JOIN Employees e
                ON sa.employee_id = e.employee_id
            JOIN Roles r
                ON sa.role_id = r.role_id
            WHERE sa.schedule_id = ?
            AND sa.shift_id = ?
            AND sa.schedule_date = ?
        """, (schedule_id, shift_id, schedule_date))

        return [
            ShiftAssignment(
                employee_name=f"{row['first_name']} {row['last_name']}",
                role_name=row["role_name"],
                hours=row["hours"]
            )
            for row in cursor.fetchall()
        ]

    def get_requirements_for_shift(self, workday_id, shift_id):

        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                sr.requirement_id,
                sr.required_count,
                r.role_name
            FROM StaffingRequirements sr
            JOIN Roles r
                ON sr.role_id = r.role_id
            WHERE sr.workday_id = ?
            AND sr.shift_id = ?
        """, (workday_id, shift_id))

        return [
            ShiftRequirement(
                role_name=row["role_name"],
                required_count=row["required_count"]
            )
            for row in cursor.fetchall()
        ]
    
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

        return [
            StaffingRequirement(
                workday_id=row["workday_id"],
                day_name=row["day_name"],
                shift_id=row["shift_id"],
                shift_name=row["shift_name"],
                role_id=row["role_id"],
                role_name=row["role_name"],
                required_count=row["required_count"]
            )
            for row in cursor.fetchall()
        ]
        
    def get_employee_hours_for_week(
    self,
    employee_id,
    week_start
    ):
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT COALESCE(
                SUM(hours),
                0
            )
            FROM ShiftAssignments
            WHERE employee_id = ?
            AND schedule_date >= ?
            AND schedule_date <= date(
                ?,
                '+7 days'
            )
        """, (
            employee_id,
            week_start,
            week_start
        ))

        return cursor.fetchone()[0]

    def get_employees_by_role(
        self,
        role_id
    ):
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM Employees
            WHERE role_id = ?
        """, (role_id,))

        return cursor.fetchall()

    def has_overlapping_assignment(
            self,
            employee_id,
            schedule_date,
            shift_id
    ):
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT 1
            FROM ShiftAssignments
            WHERE employee_id = ?
            AND schedule_date = ?
        """, (
            employee_id,
            schedule_date,
        ))

        return cursor.fetchone() is not None