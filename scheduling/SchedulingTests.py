import os
import sqlite3
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import app

from scheduling.SchedulingRepository import (
    SchedulingRepository
)

from scheduling.SchedulingService import (
    SchedulingService
)

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
                hourly_rate REAL NOT NULL
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

            CREATE TABLE StaffingRequirements(
                requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                workday_id INTEGER NOT NULL,
                shift_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                required_count INTEGER NOT NULL
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
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (101, 1, "April", "Example", 20.0)
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

        conn.commit()
        conn.close()

    def get_service(self):

        conn = sqlite3.connect(
            self.database_path
        )

        conn.row_factory = sqlite3.Row

        repository = SchedulingRepository(
            conn
        )

        service = SchedulingService(
            repository
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
    # SHIFT CRUD
    # ==================================

    def test_create_shift_persists_record(self):

        service, conn = self.get_service()

        try:

            service.create_shift(
                "Evening Shift",
                "16:00",
                "22:00"
            )

        finally:

            conn.close()

        self.assertEqual(
            self.read_rows(
                """
                SELECT shift_name
                FROM Shifts
                WHERE shift_name = ?
                """,
                ("Evening Shift",)
            ),
            [("Evening Shift",)]
        )

    def test_update_shift_updates_record(self):

        service, conn = self.get_service()

        try:

            service.update_shift(
                1,
                "Updated Shift",
                "09:00",
                "17:00"
            )

        finally:

            conn.close()

        self.assertEqual(
            self.read_rows(
                """
                SELECT shift_name
                FROM Shifts
                WHERE shift_id = 1
                """
            ),
            [("Updated Shift",)]
        )

    def test_delete_shift_removes_record(self):

        service, conn = self.get_service()

        try:

            service.delete_shift(1)

        finally:

            conn.close()

        self.assertEqual(
            self.read_rows(
                """
                SELECT *
                FROM Shifts
                """
            ),
            []
        )

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
                1,
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

    def test_workday_configuration_persists(self):

        service, conn = self.get_service()

        try:

            service.update_workday(
                1,
                False
            )

        finally:

            conn.close()

        self.assertEqual(
            self.read_rows(
                """
                SELECT active
                FROM Workdays
                WHERE workday_id = 1
                """
            ),
            [(0,)]
        )


if __name__ == "__main__":
    unittest.main()