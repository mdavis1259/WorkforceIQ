import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import app
from availability.AvailabilityRepository import (
    createAvailability,
    deleteAvailability,
    get_availability,
    getUserAvailability,
    updateAvailability,
)
from availability.AvailabilityService import availabilityDBtoEvents


class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_directory.name, "availability.db")
        self.original_config = {
            "TESTING": app.config.get("TESTING", False),
            "DATABASE": app.config.get("DATABASE"),
        }
        app.config.update(TESTING=True, DATABASE=self.database_path)
        self.create_test_database()
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

    def tearDown(self):
        self.app_context.pop()
        app.config.update(self.original_config)
        self.temp_directory.cleanup()

    def create_test_database(self):
        connection = sqlite3.connect(self.database_path)
        connection.executescript(
            """
            CREATE TABLE Users(
                userid INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                system_role_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL
            );
            CREATE TABLE Shifts(
                shift_id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_name TEXT NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE EmployeeAvailability(
                employee_availability_id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                shift_id INTEGER NOT NULL,
                availability INTEGER NOT NULL DEFAULT 1
            );
            """
        )
        connection.executemany(
            """
            INSERT INTO Users(userid, username, password, system_role_id, employee_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1, "employee", generate_password_hash("password"), 1, 101),
                (2, "another", generate_password_hash("password"), 1, 202),
            ],
        )
        connection.executemany(
            "INSERT INTO Shifts(shift_id, shift_name, start_time, end_time) VALUES (?, ?, ?, ?)",
            [
                (1, "Morning Shift", "2026-11-10T08:00:00", "2026-11-10T12:00:00"),
                (2, "Evening Shift", "2026-11-10T16:00:00", "2026-11-10T20:00:00"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO EmployeeAvailability(
                employee_availability_id, employee_id, shift_id, availability
            ) VALUES (?, ?, ?, ?)
            """,
            [(1, 101, 1, 1), (2, 202, 2, 0)],
        )
        connection.commit()
        connection.close()

    def login(self):
        response = self.client.post(
            "/login",
            data={"username": "employee", "password": "password"},
        )
        self.assertEqual(response.status_code, 302)

    def read_rows(self, query, parameters=()):
        connection = sqlite3.connect(self.database_path)
        rows = connection.execute(query, parameters).fetchall()
        connection.close()
        return rows

    def valid_availability(self, **overrides):
        data = {
            "title": "New Shift",
            "start": "2026-11-11T09:00:00",
            "end": "2026-11-11T10:00:00",
            "availability": 1,
        }
        data.update(overrides)
        return data

    def test_get_availability_returns_joined_records_for_all_employees(self):
        rows = get_availability()

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [
                (
                    row["employee_id"],
                    row["shift_name"],
                    row["start_time"],
                    row["end_time"],
                    row["active"],
                )
                for row in rows
            ],
            [
                (101, "Morning Shift", "2026-11-10T08:00:00", "2026-11-10T12:00:00", 1),
                (202, "Evening Shift", "2026-11-10T16:00:00", "2026-11-10T20:00:00", 1),
            ],
        )

    def test_get_user_availability_only_returns_the_users_employee_records(self):
        rows = getUserAvailability(1)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["employee_id"], 101)
        self.assertEqual(rows[0]["shift_name"], "Morning Shift")

    def test_create_availability_persists_shift_and_employee_record(self):
        availability_id = createAvailability(1, self.valid_availability(title="  New Shift  "))

        self.assertEqual(availability_id, 3)
        self.assertEqual(
            self.read_rows(
                """
                SELECT s.shift_name, s.start_time, s.end_time, ea.employee_id, ea.availability
                FROM EmployeeAvailability ea
                JOIN Shifts s ON s.shift_id = ea.shift_id
                WHERE ea.employee_availability_id = ?
                """,
                (availability_id,),
            ),
            [("New Shift", "2026-11-11T09:00:00", "2026-11-11T10:00:00", 101, 1)],
        )

    def test_create_availability_accepts_false_and_returns_none_for_unknown_user(self):
        availability_id = createAvailability(
            1, self.valid_availability(availability=False)
        )

        self.assertEqual(
            self.read_rows(
                "SELECT availability FROM EmployeeAvailability WHERE employee_availability_id = ?",
                (availability_id,),
            ),
            [(0,)],
        )
        self.assertIsNone(createAvailability(999, self.valid_availability()))

    def test_create_availability_rejects_invalid_payloads(self):
        invalid_payloads = [
            ([], "Request body must be a JSON object"),
            ({}, "Title must be a non-empty string"),
            (self.valid_availability(title="  "), "Title must be a non-empty string"),
            (self.valid_availability(title=1), "Title must be a non-empty string"),
            (
                self.valid_availability(start=None),
                "Start and end times are required",
            ),
            (
                self.valid_availability(end=1),
                "Start and end times are required",
            ),
            (
                self.valid_availability(availability=2),
                "Availability must be 0 or 1",
            ),
            (
                self.valid_availability(start="not-a-date"),
                "Start and end times must be valid ISO date-times",
            ),
            (
                self.valid_availability(
                    start="2026-11-11T09:00:00+00:00",
                    end="2026-11-11T10:00:00",
                ),
                "Start and end times must use the same time zone",
            ),
            (
                self.valid_availability(
                    start="2026-11-11T10:00:00",
                    end="2026-11-11T10:00:00",
                ),
                "End time must be after start time",
            ),
            (
                self.valid_availability(
                    start="2026-11-11T11:00:00",
                    end="2026-11-11T10:00:00",
                ),
                "End time must be after start time",
            ),
        ]

        for payload, message in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, message):
                    createAvailability(1, payload)

        self.assertEqual(self.read_rows("SELECT COUNT(*) FROM Shifts"), [(2,)])

    def test_update_availability_updates_shift_fields_and_availability(self):
        updated = updateAvailability(
            {
                "id": 1,
                "title": "  Updated Shift ",
                "start": "2026-11-10T09:00:00",
                "end": "2026-11-10T13:00:00",
                "availability": False,
            }
        )

        self.assertTrue(updated)
        self.assertEqual(
            self.read_rows(
                """
                SELECT s.shift_name, s.start_time, s.end_time, ea.availability
                FROM EmployeeAvailability ea
                JOIN Shifts s ON s.shift_id = ea.shift_id
                WHERE ea.employee_availability_id = 1
                """
            ),
            [("Updated Shift", "2026-11-10T09:00:00", "2026-11-10T13:00:00", 0)],
        )

    def test_update_availability_supports_availability_only_updates(self):
        self.assertTrue(updateAvailability({"id": 1, "availability": 0}))
        self.assertEqual(
            self.read_rows(
                "SELECT availability FROM EmployeeAvailability WHERE employee_availability_id = 1"
            ),
            [(0,)],
        )

    def test_update_availability_returns_false_for_unknown_record(self):
        self.assertFalse(updateAvailability({"id": 999, "title": "Updated"}))

    def test_update_availability_rejects_invalid_payloads(self):
        invalid_payloads = [
            (None, "Request body must be a JSON object"),
            ({}, "AvailabilityID is required"),
            ({"id": 1}, "No availability changes provided"),
            ({"id": 1, "title": " "}, "Title must be a non-empty string"),
            ({"id": 1, "availability": 3}, "Availability must be 0 or 1"),
        ]

        for payload, message in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, message):
                    updateAvailability(payload)

    def test_delete_availability_removes_record_and_its_shift(self):
        self.assertTrue(deleteAvailability({"id": 1}))
        self.assertEqual(
            self.read_rows("SELECT * FROM EmployeeAvailability WHERE employee_availability_id = 1"),
            [],
        )
        self.assertEqual(self.read_rows("SELECT * FROM Shifts WHERE shift_id = 1"), [])

    def test_delete_availability_returns_false_for_unknown_record(self):
        self.assertFalse(deleteAvailability({"id": 999}))

    def test_delete_availability_rejects_invalid_payloads(self):
        for payload, message in (
            (None, "Request body must be a JSON object"),
            ({}, "AvailabilityID is required"),
        ):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, message):
                    deleteAvailability(payload)

    def test_availability_db_rows_are_converted_to_calendar_events(self):
        events = availabilityDBtoEvents(get_availability())

        self.assertEqual(
            events,
            [
                {
                    "id": 1,
                    "title": "Morning Shift",
                    "start": "2026-11-10T08:00:00",
                    "end": "2026-11-10T12:00:00",
                    "color": "green",
                },
                {
                    "id": 2,
                    "title": "Evening Shift",
                    "start": "2026-11-10T16:00:00",
                    "end": "2026-11-10T20:00:00",
                    "color": "red",
                },
            ],
        )
        self.assertEqual(availabilityDBtoEvents([]), [])

    def test_availability_page_renders_only_logged_in_users_events(self):
        self.login()

        response = self.client.get("/availability")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"title: 'Morning Shift'", response.data)
        self.assertNotIn(b"Evening Shift", response.data)

    def test_availability_route_creates_updates_and_deletes_events(self):
        self.login()
        created = self.client.post(
            "/availability",
            json=self.valid_availability(),
        )
        self.assertEqual(created.status_code, 201)
        availability_id = created.get_json()["id"]

        updated = self.client.post(
            "/availability",
            json={"id": availability_id, "title": "Route Updated", "availability": 0},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["status"], "success")

        deleted = self.client.delete("/availability", json={"id": availability_id})
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.get_json()["status"], "success")

    def test_availability_route_reports_validation_and_missing_record_errors(self):
        self.login()

        invalid_create = self.client.post("/availability", json={})
        self.assertEqual(invalid_create.status_code, 400)
        self.assertEqual(invalid_create.get_json()["status"], "error")

        invalid_update = self.client.post("/availability", json={"id": 1, "title": ""})
        self.assertEqual(invalid_update.status_code, 400)

        invalid_delete = self.client.delete("/availability", json={})
        self.assertEqual(invalid_delete.status_code, 400)

        missing_update = self.client.post(
            "/availability", json={"id": 999, "title": "Missing"}
        )
        self.assertEqual(missing_update.status_code, 404)

        missing_delete = self.client.delete("/availability", json={"id": 999})
        self.assertEqual(missing_delete.status_code, 404)

    def test_availability_route_reports_unknown_user_during_creation(self):
        self.login()

        with patch(
            "availability.AvailabilityRoutes.createAvailability", return_value=None
        ):
            response = self.client.post(
                "/availability", json=self.valid_availability()
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["message"], "User not found")


if __name__ == "__main__":
    unittest.main()