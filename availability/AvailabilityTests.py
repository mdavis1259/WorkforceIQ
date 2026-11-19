import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import app
from availability.AvailabilityRepository import AvailabilityRepository
from availability.AvailabilityService import AvailabilityService
from employee_management.EmployeeRepository import EmployeeRepository
from employee_management.EmployeeService import EmployeeService
from shared.exceptions import ValidationError
class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.connections = []
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
        for connection in self.connections:
            connection.close()
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
                employee_id INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                force_password_reset INTEGER NOT NULL DEFAULT 0
            );
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
            CREATE TABLE Qualifications(
                qualification_id INTEGER PRIMARY KEY,
                qualification_name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE EmployeeQualifications(
                employee_id INTEGER NOT NULL,
                qualification_id INTEGER NOT NULL,
                PRIMARY KEY (employee_id, qualification_id)
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
            "INSERT INTO Roles VALUES (?, ?, ?)",
            [(1, "Associate", 1), (2, "Manager", 2)],
        )
        connection.executemany(
            """
            INSERT INTO Employees(employee_id, role_id, first_name, last_name, hourly_rate)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (101, 1, "April", "Example", 20.0),
                (202, 2, "Bob", "Example", 25.0),
            ],
        )
        connection.executemany(
            """
            INSERT INTO Users(userid, username, password, system_role_id, employee_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1, "employee", generate_password_hash("password"), 1, 101),
                (2, "another", generate_password_hash("password"), 2, 202),
                (3, "administrator", generate_password_hash("password"), 3, 202),
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

    def get_service(self):
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        self.connections.append(conn)

        repository = AvailabilityRepository(conn)
        employee_repository = EmployeeRepository(conn)
        employee_service = EmployeeService(employee_repository)
        service = AvailabilityService(repository, employee_service)

        return service, conn

    def login(self):
        response = self.client.post(
            "/login",
            data={"username": "employee", "password": "password"},
        )
        self.assertEqual(response.status_code, 302)

    def login_manager(self):
        response = self.client.post(
            "/login",
            data={"username": "another", "password": "password"},
        )
        self.assertEqual(response.status_code, 302)

    def login_administrator(self):
        response = self.client.post(
            "/login",
            data={"username": "administrator", "password": "password"},
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
        service, conn = self.get_service()
        
        rows = service.get_availability()

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [
                (
                    row["employee_id"],
                    row["shift_name"],
                    row["start_time"],
                    row["end_time"],
                )
                for row in rows
            ],
            [
                (101, "Morning Shift", "2026-11-10T08:00:00", "2026-11-10T12:00:00"),
                (202, "Evening Shift", "2026-11-10T16:00:00", "2026-11-10T20:00:00"),
            ],
        )

    def test_get_user_availability_only_returns_the_users_employee_records(self):
        service, conn = self.get_service()
        rows = service.get_employee_availability(101)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["employee_id"], 101)
        self.assertEqual(rows[0]["shift_name"], "Morning Shift")

    def test_create_availability_persists_shift_and_employee_record(self):
        service, conn = self.get_service()
        availability_id = service.create_availability(101, self.valid_availability(title="  New Shift  "))

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
        service, conn = self.get_service()
        availability_id = service.create_availability(
            101, self.valid_availability(availability=False)
        )

        self.assertEqual(
            self.read_rows(
                "SELECT availability FROM EmployeeAvailability WHERE employee_availability_id = ?",
                (availability_id,),
            ),
            [(0,)],
        )
        self.assertIsNone(service.create_availability(999, self.valid_availability()))

    def test_unknown_employee_does_not_create_shift_or_availability(self):
        service, conn = self.get_service()
        self.assertIsNone(service.create_availability(999, self.valid_availability()))
        self.assertEqual(self.read_rows("SELECT COUNT(*) FROM Shifts"), [(2,)])
        self.assertEqual(self.read_rows("SELECT COUNT(*) FROM EmployeeAvailability"), [(2,)])

    def test_recurring_creation_rolls_back_after_insert_failure(self):
        service, conn = self.get_service()
        conn.executescript(
            """
            CREATE TRIGGER reject_second_occurrence
            BEFORE INSERT ON EmployeeAvailability
            WHEN (SELECT start_time FROM Shifts WHERE shift_id = NEW.shift_id)
                 = '2026-11-18T09:00:00'
            BEGIN
                SELECT RAISE(ABORT, 'rejected occurrence');
            END;
            """
        )

        with self.assertRaisesRegex(sqlite3.IntegrityError, "rejected occurrence"):
            service.create_availability(
                101,
                self.valid_availability(recurrence="weekly", recurrence_until="2026-11-18"),
            )

        self.assertEqual(self.read_rows("SELECT COUNT(*) FROM Shifts"), [(2,)])
        self.assertEqual(self.read_rows("SELECT COUNT(*) FROM EmployeeAvailability"), [(2,)])

    def test_create_availability_rejects_invalid_payloads(self):
        service, conn = self.get_service()
        
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
                "Availability must be False or True",
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
                    service.create_availability(101, payload)

        self.assertEqual(self.read_rows("SELECT COUNT(*) FROM Shifts"), [(2,)])

    def test_create_weekly_availability_repeats_until_end_date(self):
        service, conn = self.get_service()
        availability_id = service.create_availability(
            101,
            self.valid_availability(
                recurrence="weekly",
                recurrence_until="2026-11-25",
            ),
        )

        self.assertEqual(availability_id, 3)
        self.assertEqual(
            self.read_rows(
                """
                SELECT s.start_time, s.end_time
                FROM EmployeeAvailability ea
                JOIN Shifts s ON s.shift_id = ea.shift_id
                WHERE ea.employee_id = 101 AND s.shift_name = ?
                ORDER BY s.start_time
                """,
                ("New Shift",),
            ),
            [
                ("2026-11-11T09:00:00", "2026-11-11T10:00:00"),
                ("2026-11-18T09:00:00", "2026-11-18T10:00:00"),
                ("2026-11-25T09:00:00", "2026-11-25T10:00:00"),
            ],
        )

    def test_create_monthly_availability_preserves_end_of_month_dates(self):
        service, conn = self.get_service()
        availability_id = service.create_availability(
            101,
            self.valid_availability(
                start="2026-01-31T09:00:00",
                end="2026-01-31T10:00:00",
                recurrence="monthly",
                recurrence_until="2026-04-30",
            ),
        )

        self.assertEqual(availability_id, 3)
        self.assertEqual(
            self.read_rows(
                """
                SELECT s.start_time
                FROM EmployeeAvailability ea
                JOIN Shifts s ON s.shift_id = ea.shift_id
                WHERE ea.employee_id = 101 AND s.shift_name = ?
                ORDER BY s.start_time
                """,
                ("New Shift",),
            ),
            [
                ("2026-01-31T09:00:00",),
                ("2026-02-28T09:00:00",),
                ("2026-03-31T09:00:00",),
                ("2026-04-30T09:00:00",),
            ],
        )

    def test_create_recurring_availability_requires_end_date(self):
        with self.assertRaisesRegex(
            ValueError, "A recurrence end date is required"
        ):
            service, conn = self.get_service()
            service.create_availability(
                101,
                self.valid_availability(recurrence="weekly"),
            )

    def test_create_availability_rejects_recurrence_end_before_start(self):
        with self.assertRaisesRegex(
            ValueError, "Recurrence end date must be on or after the event date"
        ):
            service, conn = self.get_service()
            service.create_availability(
                101,
                self.valid_availability(
                    recurrence="monthly",
                    recurrence_until="2026-11-10",
                ),
            )

    def test_update_availability_updates_shift_fields_and_availability(self):
        service, conn = self.get_service()
        updated = service.update_availability(
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
        service, conn = self.get_service()
        self.assertTrue(service.update_availability({"id": 1, "availability": 0}))
        self.assertEqual(
            self.read_rows(
                "SELECT availability FROM EmployeeAvailability WHERE employee_availability_id = 1"
            ),
            [(0,)],
        )

    def test_update_availability_returns_false_for_unknown_record(self):
        service, conn = self.get_service()
        self.assertFalse(service.update_availability({"id": 999, "title": "Updated"}))

    def test_update_availability_rejects_invalid_payloads(self):
        service, conn = self.get_service()
        invalid_payloads = [
            (None, "Request body must be a JSON object"),
            ({}, "AvailabilityID is required"),
            ({"id": 1}, "No availability changes provided"),
            ({"id": 1, "title": " "}, "Title must be a non-empty string"),
            ({"id": 1, "availability": 3}, "Availability must be False or True"),
        ]

        for payload, message in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, message):
                    service.update_availability(payload)

    def test_delete_availability_removes_record_and_its_shift(self):
        service, conn = self.get_service()
        self.assertTrue(service.delete_availability({"id": 1}))
        self.assertEqual(
            self.read_rows("SELECT * FROM EmployeeAvailability WHERE employee_availability_id = 1"),
            [],
        )
        self.assertEqual(self.read_rows("SELECT * FROM Shifts WHERE shift_id = 1"), [])

    def test_delete_availability_returns_false_for_unknown_record(self):
        service, conn = self.get_service()
        self.assertFalse(service.delete_availability({"id": 999}))

    def test_delete_availability_rejects_invalid_payloads(self):
        service, conn = self.get_service()
        for payload, message in (
            (None, "Request body must be a JSON object"),
            ({}, "AvailabilityID is required"),
        ):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, message):
                    service.delete_availability(payload)

    def test_availability_db_rows_are_converted_to_calendar_events(self):
        service, conn = self.get_service()
        events = service.availability_db_to_events(service.get_availability())

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
        self.assertEqual(service.availability_db_to_events([]), [])

    def test_availability_page_renders_only_logged_in_users_events(self):
        self.login()

        response = self.client.get("/availability")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"title: 'Morning Shift'", response.data)
        self.assertNotIn(b"Evening Shift", response.data)
        self.assertIn(b'id="modalRecurrence"', response.data)
        self.assertIn(b'id="cancelCreateEventBtn" type="button" hidden>Cancel', response.data)
        self.assertIn(b'value="weekly">Weekly', response.data)
        self.assertIn(b'value="monthly">Monthly', response.data)

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
            "availability.AvailabilityService.AvailabilityService.create_availability_series",
            return_value=None,
        ):
            response = self.client.post(
                "/availability", json=self.valid_availability()
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["message"], "Employee not found")

    def test_availability_route_rejects_unknown_employee_without_writes(self):
        self.login_administrator()
        with self.client.session_transaction() as session:
            session["availability_employee"] = 999

        response = self.client.post("/availability", json=self.valid_availability())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["message"], "Employee not found")
        self.assertEqual(self.read_rows("SELECT COUNT(*) FROM Shifts"), [(2,)])
        self.assertEqual(self.read_rows("SELECT COUNT(*) FROM EmployeeAvailability"), [(2,)])

    def test_routes_close_connections_after_success_redirect_and_error(self):
        self.login()
        connections = []

        def open_connection():
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            connections.append(conn)
            return conn

        with patch("availability.AvailabilityRoutes.get_db_connection", side_effect=open_connection):
            self.assertEqual(self.client.get("/availability").status_code, 200)
            self.assertEqual(self.client.get("/avail_select").status_code, 302)
            self.assertEqual(self.client.post("/availability", json={}).status_code, 400)
            with patch.object(AvailabilityService, "get_employee_availability",
                              side_effect=RuntimeError("test failure")):
                with self.assertRaisesRegex(RuntimeError, "test failure"):
                    self.client.get("/availability")
            with patch("availability.AvailabilityRoutes._build_availability_service",
                       side_effect=RuntimeError("construction failure")):
                for url in ("/availability", "/avail_select"):
                    with self.subTest(url=url):
                        with self.assertRaisesRegex(RuntimeError, "construction failure"):
                            self.client.get(url)

        self.assertEqual(len(connections), 6)
        for conn in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")

    def test_associate_availability_selector_redirects_to_own_availability(self):
        self.login()
        with self.client.session_transaction() as session:
            session["availability_employee"] = 202

        response = self.client.get("/avail_select")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/availability")
        with self.client.session_transaction() as session:
            self.assertEqual(session["availability_employee"], 101)

    def test_manager_availability_selector_lists_employees(self):
        self.login_manager()

        response = self.client.get("/avail_select")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"April Example (ID: 101)", response.data)
        self.assertNotIn(b"Bob Example (ID: 202)", response.data)
        self.assertIn(b"My Availability", response.data)

    def test_manager_selection_saves_employee_and_redirects(self):
        self.login_manager()

        response = self.client.post(
            "/avail_select", data={"employee_id": "101"}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/availability")
        with self.client.session_transaction() as session:
            self.assertEqual(session["availability_employee"], 101)

    def test_manager_can_select_own_availability(self):
        self.login_manager()

        response = self.client.post(
            "/avail_select", data={"employee_id": "202"}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/availability")
        with self.client.session_transaction() as session:
            self.assertEqual(session["availability_employee"], 202)

        page = self.client.get("/availability")
        self.assertEqual(page.status_code, 200)

        created = self.client.post(
            "/availability", json=self.valid_availability()
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(
            self.read_rows(
                "SELECT employee_id FROM EmployeeAvailability WHERE employee_id = 202"
            )[-1][0],
            202,
        )

    def test_manager_cannot_open_unknown_availability_with_stale_session(self):
        self.login_manager()
        with self.client.session_transaction() as session:
            session["availability_employee"] = 999

        response = self.client.get("/availability")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/avail_select")
        with self.client.session_transaction() as session:
            self.assertNotIn("availability_employee", session)

    def test_manager_cannot_select_an_unknown_employee(self):
        self.login_manager()

        response = self.client.post(
            "/avail_select", data={"employee_id": "999"}
        )

        self.assertEqual(response.status_code, 400)

    def test_administrator_can_select_any_employee_level(self):
        self.login_administrator()

        selector_response = self.client.get("/avail_select")
        self.assertEqual(selector_response.status_code, 200)
        self.assertIn(b"April Example (ID: 101)", selector_response.data)
        self.assertIn(b"Bob Example (ID: 202)", selector_response.data)

        response = self.client.post(
            "/avail_select", data={"employee_id": "202"}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/availability")
        with self.client.session_transaction() as session:
            self.assertEqual(session["availability_employee"], 202)


if __name__ == "__main__":
    unittest.main()