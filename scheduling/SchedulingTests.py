import os
import sqlite3
import tempfile
import unittest

from availability.AvailabilityService import AvailabilityService
from availability.AvailabilityRepository import AvailabilityRepository
from werkzeug.security import generate_password_hash

from app import app

from employee_management.EmployeeRepository import EmployeeRepository
from employee_management.EmployeeService import EmployeeService

from scheduling.SchedulingRepository import (
    SchedulingRepository
)

from scheduling.SchedulingService import (
    SchedulingService
)
from scheduling.SchedulingRoutes import _build_scheduling_service

from shared.exceptions import ValidationError

class SchedulingTests(unittest.TestCase):

    def setUp(self):

        self.temp_directory = tempfile.TemporaryDirectory()

        self.database_path = os.path.join(
            self.temp_directory.name,
            "scheduling.db"
        )

        self.original_config = {
            "TESTING": app.config.get("TESTING", False),
            "DATABASE": app.config.get("DATABASE")
        }

        app.config.update(
            TESTING=True,
            DATABASE=self.database_path
        )

        self.create_test_database()

        self.app_context = app.app_context()
        self.app_context.push()

        self.client = app.test_client()

    def tearDown(self):

        self.app_context.pop()

        app.config.update(
            self.original_config
        )

        self.temp_directory.cleanup()

    def create_test_database(self):

        conn = sqlite3.connect(
            self.database_path
        )

        conn.executescript(
            """
            CREATE TABLE Roles(
                role_id INTEGER PRIMARY KEY,
                role_name TEXT NOT NULL,
                system_role_id INTEGER NOT NULL
            );

            CREATE TABLE Employees(
                employee_id INTEGER PRIMARY KEY,
                role_id INTEGER NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                hourly_rate REAL NOT NULL,
                max_hours_per_week INTEGER NOT NULL DEFAULT 40,
                preferred_hours_per_week INTEGER NOT NULL DEFAULT 32,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE Users(
                userid INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                system_role_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL
            );

            CREATE TABLE Workdays(
                workday_id INTEGER PRIMARY KEY,
                day_name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE Shifts(
                shift_id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL
            );

            CREATE TABLE EmployeeAvailability(
                employee_availability_id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                shift_id INTEGER NOT NULL,
                workday_id INTEGER NOT NULL,
                availability INTEGER NOT NULL DEFAULT 2,
                FOREIGN KEY (employee_id) REFERENCES Employees(employee_id),
                FOREIGN KEY (shift_id) REFERENCES Shifts(shift_id),
                FOREIGN KEY (workday_id) REFERENCES Workdays(workday_id),
                CHECK (availability IN (0, 1, 2))
            );

            CREATE TABLE StaffingRequirements(
                requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                workday_id INTEGER NOT NULL,
                shift_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                required_count INTEGER NOT NULL
            );

            CREATE TABLE Schedules(
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Draft'
            );

            CREATE TABLE ShiftAssignments(
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,

                schedule_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                shift_id INTEGER NOT NULL,

                schedule_date TEXT NOT NULL,
                hours REAL NOT NULL
            );
            """
        )

        conn.executemany(
            """
            INSERT INTO Workdays
            VALUES (?, ?, ?)
            """,
            [
                (1, "Monday", 1),
                (2, "Tuesday", 1),
                (3, "Wednesday", 1),
                (4, "Thursday", 1),
                (5, "Friday", 1)
            ]
        )

        conn.executemany(
            """
            INSERT INTO Roles
            VALUES (?, ?, ?)
            """,
            [
                (1, "Associate", 1),
                (2, "Manager", 2)
            ]
        )

        conn.executemany(
            """
            INSERT INTO Employees
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (101, 1, "April", "Example", 20.0, 40, 32, 1)
            ]
        )

        conn.executemany(
            """
            INSERT INTO Users
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    "manager",
                    generate_password_hash(
                        "password"
                    ),
                    2,
                    101
                )
            ]
        )

        conn.execute(
            """
            INSERT INTO Shifts(
                shift_id,
                shift_name,
                start_time,
                end_time
            )
            VALUES (
                1,
                'Morning Shift',
                '08:00',
                '16:00'
            )
            """
        )

        conn.execute(
            """
            INSERT INTO EmployeeAvailability(employee_id, shift_id, workday_id, availability)
            VALUES (101, 1, 1, 1)
            """
        )

        conn.commit()
        conn.close()

    def test_scheduling_route_service_builder_wires_availability(self):
        service, conn = _build_scheduling_service()
        try:
            self.assertIs(
                service.availability_service.employee_service,
                service.employee_service,
            )
            self.assertTrue(service.availability_service.is_employee_available(101, 1, 1))
        finally:
            conn.close()

    def get_service(self):

        conn = sqlite3.connect(
            self.database_path
        )

        conn.row_factory = sqlite3.Row

        repository = SchedulingRepository(
            conn
        )

        employee_service = EmployeeService(
            EmployeeRepository(conn)
        )

        availability_service = AvailabilityService(
            AvailabilityRepository(conn), employee_service
        )

        forecasting_service = None

        service = SchedulingService(
            repository, employee_service, forecasting_service, availability_service
        )

        return service, conn

    def read_rows(
        self,
        query,
        parameters=()
    ):

        conn = sqlite3.connect(
            self.database_path
        )

        rows = conn.execute(
            query,
            parameters
        ).fetchall()

        conn.close()

        return rows

    # ==================================
    # STAFFING REQUIREMENTS
    # ==================================

    def test_create_staffing_requirement(self):

        service, conn = self.get_service()

        try:

            service.create_staffing_requirement(
                1,
                1,
                1,
                5
            )

        finally:

            conn.close()

        self.assertEqual(
            self.read_rows(
                """
                SELECT required_count
                FROM StaffingRequirements
                """
            ),
            [(5,)]
        )

    def test_duplicate_staffing_requirement_ignored(self):

        service, conn = self.get_service()

        try:

            service.create_staffing_requirement(
                1,
                1,
                1,
                5
            )

            service.create_staffing_requirement(
                1,
                1,
                1,
                5
            )

        finally:

            conn.close()

        self.assertEqual(
            self.read_rows(
                """
                SELECT COUNT(*)
                FROM StaffingRequirements
                """
            ),
            [(1,)]
        )

    def test_update_staffing_requirement_updates_count(self):

        service, conn = self.get_service()

        try:

            service.create_staffing_requirement(
                1,
                1,
                1,
                5
            )

            service.update_staffing_requirement(
                1,
                6
            )

        finally:

            conn.close()

        self.assertEqual(
            self.read_rows(
                """
                SELECT DISTINCT required_count
                FROM StaffingRequirements
                """
            ),
            [(6,)]
        )

    def test_delete_staffing_requirement_removes_rule(self):

        service, conn = self.get_service()

        try:

            service.create_staffing_requirement(
                1,
                1,
                1,
                5
            )

            service.delete_staffing_requirement(
                1
            )

        finally:

            conn.close()

        self.assertEqual(
            self.read_rows(
                """
                SELECT *
                FROM StaffingRequirements
                """
            ),
            []
        )

    # ==================================
    # VALIDATION
    # ==================================

    def test_shift_name_required(self):

        service, conn = self.get_service()

        try:

            with self.assertRaises(
                ValidationError
            ):
                service.create_shift(
                    "",
                    "08:00",
                    "16:00"
                )

        finally:

            conn.close()

    def test_required_count_must_be_positive(self):

        service, conn = self.get_service()

        try:

            with self.assertRaises(
                ValidationError
            ):
                service.create_staffing_requirement(
                    1,
                    1,
                    1,
                    0
                )

        finally:

            conn.close()

    def test_create_schedule_persists_record(self):

        service, conn = self.get_service()

        try:

            service.create_schedule("2026-11-09")

        finally:
            conn.close()

        self.assertEqual(
            self.read_rows(
                """
                SELECT week_start
                FROM Schedules
                """
            ),
            [("2026-11-09",)]
        )

    def test_get_schedule_returns_schedule(self):

        service, conn = self.get_service()

        try:

            service.create_schedule("2026-11-09")

            schedule = service.get_schedule("2026-11-09")
        
        finally:
            conn.close()

        self.assertIsNotNone(schedule)

        self.assertEqual(schedule.week_start, "2026-11-09")
    
    def test_create_assignment_persists_record(self):
        
        service, conn = self.get_service()

        try:

            schedule = service.create_schedule("2026-11-09")

            service.create_assignment(
                schedule.schedule_id,
                101,
                1,
                1,
                "2026-11-09",
                8
            )
        
        finally:
            conn.close()

        self.assertEqual(
            self.read_rows(
                """
                SELECT employee_id
                FROM ShiftAssignments
                """
            ),
            [(101,)]
        )

    def test_get_assignments_returns_rows(self):
        
        service, conn = self.get_service()

        try:

            schedule = service.create_schedule("2026-11-09")

            service.create_assignment(
                schedule.schedule_id,
                101,
                1,
                1,
                "2026-11-09",
                8
            )

            assignments = service.get_assignments(schedule.schedule_id)
        
        finally:
            conn.close()
        
        self.assertEqual(len(assignments), 1)

        self.assertEqual(assignments[0]["employee_id"], 101)

    def test_generate_week_creates_schedule(self):

        service, conn = self.get_service()

        try:

            schedule, _ = service.generate_week("2026-11-09")

        finally:
            conn.close()

        self.assertIsNotNone(schedule)

        self.assertEqual(schedule.week_start, "2026-11-09")

        self.assertEqual(
            self.read_rows(
                """
                SELECT COUNT(*)
                FROM Schedules
                """
            ),
            [(1,)]
        )

    def test_generate_week_creates_assignments(self):

        service, conn = self.get_service()

        try:

            service.create_staffing_requirement(
                1,
                1,
                1,
                2
            )

            schedule, _ = service.generate_week(
                "2026-11-09"
            )

            assignments = service.get_assignments(
                schedule.schedule_id
            )

        finally:

            conn.close()

        self.assertEqual(
            len(assignments),
            1
        )

    def test_generate_week_assigns_employee_by_role(self):

        service, conn = self.get_service()

        try:

            # Associate staffing requirement
            service.create_staffing_requirement(
                1,  # Monday
                1,  # Morning Shift
                1,  # Associate Role
                1
            )

            schedule, _ = service.generate_week(
                "2026-11-09"
            )

            assignments = service.get_assignments(
                schedule.schedule_id
            )

        finally:

            conn.close()

        self.assertEqual(
            len(assignments),
            1
        )

        # Verify assigned employee is the Associate
        self.assertEqual(
            assignments[0]["employee_id"],
            101
        )

        self.assertEqual(
            assignments[0]["role_id"],
            1
        )

    def test_generate_week_skips_role_with_no_qualified_employee(self):

        service, conn = self.get_service()

        try:

            # Manager role requirement
            service.create_staffing_requirement(
                1,  # Monday
                1,  # Morning Shift
                2,  # Manager Role
                1
            )

            # Remove all managers
            conn.execute("""
                DELETE FROM Employees
                WHERE role_id = 2
            """)
            conn.commit()

            schedule, _ = service.generate_week(
                "2026-11-09"
            )

            assignments = service.get_assignments(
                schedule.schedule_id
            )

        finally:

            conn.close()

        self.assertEqual(
            len(assignments),
            0
        )

    def test_generate_week_skips_unavailable_employee(self):

        service, conn = self.get_service()

        try:
            conn.execute(
                "UPDATE EmployeeAvailability SET availability = 0 "
                "WHERE employee_id = 101 AND shift_id = 1 AND workday_id = 1"
            )
            conn.commit()

            service.create_staffing_requirement(
                1,  # Monday
                1,  # Morning Shift
                1,  # Associate
                1
            )

            schedule, _ = service.generate_week(
                "2026-11-09"
            )

            assignments = service.get_assignments(
                schedule.schedule_id
            )

        finally:

            conn.close()

        self.assertEqual(
            len(assignments),
            0
        )

    def test_generate_week_skips_employee_without_matching_availability(self):
        service, conn = self.get_service()
        try:
            conn.execute("DELETE FROM EmployeeAvailability WHERE workday_id = 1")
            conn.commit()
            service.create_staffing_requirement(1, 1, 1, 1)

            schedule, _ = service.generate_week("2026-11-09")
            assignments = service.get_assignments(schedule.schedule_id)
        finally:
            conn.close()

        self.assertEqual(len(assignments), 0)
    
    def test_generate_week_skips_employee_exceeding_weekly_hour_limit(self):

        service, conn = self.get_service()

        try:

            schedule = service.create_schedule(
                "2026-11-09"
            )

            # Employee already at max weekly hours
            service.create_assignment(
                schedule.schedule_id,
                101,
                1,
                1,
                "2026-11-09",
                40
            )

            service.create_staffing_requirement(
                1,  # Monday
                1,  # Morning Shift
                1,  # Associate
                1
            )

            generated_schedule, _ = service.generate_week(
                "2026-11-09"
            )

            assignments = service.get_assignments(
                generated_schedule.schedule_id
            )

        finally:

            conn.close()

        self.assertEqual(
            len(assignments),
            1
        )

    def test_get_employee_hours_for_week(self):

        service, conn = self.get_service()

        try:

            schedule = service.create_schedule("2026-11-09")

            service.create_assignment(
                schedule.schedule_id,
                101,
                1,
                1,
                "2026-11-09",
                8
            )

            service.create_assignment(
                schedule.schedule_id,
                101,
                1,
                1,
                "2026-11-10",
                8
            )

            hours = service.scheduling_repository.get_employee_hours_for_week(101, "2026-11-09")
        
        finally:
            conn.close()

        self.assertEqual(hours, 16)        

    def test_generate_week_prevents_overlapping_assignments(self):

        service, conn = self.get_service()

        try:

            # Existing shift
            service.create_staffing_requirement(
                1,  # Monday
                1,  # Morning Shift
                1,  # Associate
                1
            )

            schedule = service.create_schedule(
                "2026-11-09"
            )

            service.create_assignment(
                schedule.schedule_id,
                101,
                1,
                1,
                "2026-11-09",
                8
            )

            # Add a second overlapping shift
            conn.execute(
                """
                INSERT INTO Shifts(
                    shift_id,
                    shift_name,
                    start_time,
                    end_time
                )
                VALUES(
                    2,
                    'Overlapping Shift',
                    '12:00',
                    '20:00'
                )
                """
            )

            conn.execute(
                """
                INSERT INTO EmployeeAvailability(employee_id, shift_id, workday_id, availability)
                VALUES (101, 2, 1, 1)
                """
            )
            conn.commit()

            service.create_staffing_requirement(
                1,  # Monday
                2,  # Overlapping Shift
                1,  # Associate
                1
            )

            generated_schedule, _ = service.generate_week(
                "2026-11-09"
            )

            assignments = service.get_assignments(
                generated_schedule.schedule_id
            )

        finally:

            conn.close()

        self.assertFalse(
            any(
                assignment["shift_id"] == 2
                for assignment in assignments
            )
        )

if __name__ == "__main__":
    unittest.main()