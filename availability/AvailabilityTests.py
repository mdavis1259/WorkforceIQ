import os
import sqlite3
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import app
from availability.AvailabilityRepository import AvailabilityRepository
from availability.AvailabilityService import AvailabilityService
from employee_management.EmployeeRepository import EmployeeRepository
from employee_management.EmployeeService import EmployeeService


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
            CREATE TABLE SystemRoles(
                system_role_id INTEGER PRIMARY KEY,
                role_name TEXT NOT NULL UNIQUE,
                description TEXT
            );
            CREATE TABLE Roles(
                role_id INTEGER PRIMARY KEY,
                role_name TEXT NOT NULL UNIQUE,
                system_role_id INTEGER NOT NULL,
                FOREIGN KEY (system_role_id) REFERENCES SystemRoles(system_role_id)
            );
            CREATE TABLE Employees(
                employee_id INTEGER PRIMARY KEY,
                role_id INTEGER NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                hourly_rate REAL NOT NULL,
                max_hours_per_week INTEGER NOT NULL DEFAULT 40,
                preferred_hours_per_week INTEGER NOT NULL DEFAULT 32,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (role_id) REFERENCES Roles(role_id)
            );
            CREATE TABLE Qualifications(
                qualification_id INTEGER PRIMARY KEY,
                qualification_name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE EmployeeQualifications(
                employee_id INTEGER NOT NULL,
                qualification_id INTEGER NOT NULL,
                PRIMARY KEY (employee_id, qualification_id),
                FOREIGN KEY (employee_id) REFERENCES Employees(employee_id),
                FOREIGN KEY (qualification_id)
                    REFERENCES Qualifications(qualification_id)
            );
            CREATE TABLE Users(
                userid INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                system_role_id INTEGER NOT NULL DEFAULT 0,
                employee_id INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                force_password_reset INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (system_role_id)
                    REFERENCES SystemRoles(system_role_id),
                FOREIGN KEY (employee_id) REFERENCES Employees(employee_id)
            );
            CREATE TABLE Workdays(
                workday_id INTEGER PRIMARY KEY,
                day_name TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE Shifts(
                shift_id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_name TEXT NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL
            );
            CREATE TABLE EmployeeAvailability(
                employee_availability_id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                shift_id INTEGER NOT NULL,
                workday_id INTEGER NOT NULL,
                availability INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (employee_id) REFERENCES Employees(employee_id),
                FOREIGN KEY (shift_id) REFERENCES Shifts(shift_id),
                FOREIGN KEY (workday_id) REFERENCES Workdays(workday_id),
                CHECK (availability IN (0, 1, 2))
            );
            """
        )
        connection.executemany(
            "INSERT INTO SystemRoles VALUES (?, ?, ?)",
            [
                (1, "Associate", "Regular employee"),
                (2, "Manager", "Manager"),
                (3, "Administrator", "Administrator"),
            ],
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
            "INSERT INTO Workdays(workday_id, day_name) VALUES (?, ?)",
            [
                (1, "Monday"),
                (2, "Tuesday"),
                (3, "Wednesday"),
                (4, "Thursday"),
                (5, "Friday"),
                (6, "Saturday"),
                (7, "Sunday"),
            ],
        )
        connection.executemany(
            "INSERT INTO Shifts(shift_id, shift_name, start_time, end_time) VALUES (?, ?, ?, ?)",
            [
                (1, "Morning Shift", "08:00", "12:00"),
                (2, "Evening Shift", "16:00", "20:00"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO EmployeeAvailability(
                employee_availability_id, employee_id, shift_id, workday_id, availability
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [(1, 101, 1, 2, 1), (2, 202, 2, 2, 0)],
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
        return AvailabilityService(repository, employee_service), conn

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
        try:
            return connection.execute(query, parameters).fetchall()
        finally:
            connection.close()

    def calendar_event(self, **overrides):
        data = {
            "id": "",
            "shift_name": "Morning Shift",
            "start": "2026-11-23T08:00:00Z",
            "end": "2026-11-23T12:00:00Z",
            "start_timezone_offset": 0,
            "end_timezone_offset": 0,
            "availability": 0,
        }
        data.update(overrides)
        return data

    def test_format_shift_time_normalizes_iso_times_and_datetimes(self):
        for value, expected in (
            ("08:00", "08:00"),
            ("08:00:00", "08:00"),
            ("2026-11-20T08:00:00", "08:00"),
            ("2026-11-20 16:30:00", "16:30"),
        ):
            with self.subTest(value=value):
                self.assertEqual(AvailabilityService.format_shift_time(value), expected)

    def test_format_shift_time_rejects_invalid_values(self):
        for value in (None, "", "25:00", "08:00:01", "08:00:00+00:00"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    AvailabilityService.format_shift_time(value)

    def test_get_availability_returns_joined_records_for_all_employees(self):
        service, _ = self.get_service()

        rows = service.get_availability()

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
                (101, "Morning Shift", "08:00", "12:00"),
                (202, "Evening Shift", "16:00", "20:00"),
            ],
        )

    def test_get_employee_availability_filters_by_employee(self):
        service, _ = self.get_service()

        rows = service.get_employee_availability(101)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["employee_id"], 101)
        self.assertEqual(rows[0]["shift_name"], "Morning Shift")

    def test_list_employees_can_filter_to_associates(self):
        service, _ = self.get_service()

        all_employees = service.list_employees()
        associates = service.list_employees(associates_only=True)

        self.assertEqual(
            [employee.employee_id for employee in all_employees],
            [101, 202],
        )
        self.assertEqual(
            [employee.employee_id for employee in associates],
            [101],
        )

    def test_create_availability_inserts_using_shift_and_workday_ids(self):
        service, _ = self.get_service()

        availability_id = service.create_availability(101, 1, 1, 0)

        self.assertEqual(availability_id, 3)
        self.assertEqual(
            self.read_rows(
                """
                SELECT employee_id, shift_id, workday_id, availability
                FROM EmployeeAvailability WHERE employee_availability_id = ?
                """,
                (availability_id,),
            ),
            [(101, 1, 1, 0)],
        )

    def test_create_availability_updates_a_matching_employee_shift_and_day(self):
        service, _ = self.get_service()

        availability_id = service.create_availability(101, 1, 2, 2)

        self.assertEqual(availability_id, 1)
        self.assertEqual(
            self.read_rows(
                """
                SELECT COUNT(*), MIN(availability)
                FROM EmployeeAvailability
                WHERE employee_id = 101 AND shift_id = 1 AND workday_id = 2
                """
            ),
            [(1, 2)],
        )

    def test_database_rejects_availability_values_outside_the_schema_constraint(self):
        service, _ = self.get_service()

        with self.assertRaises(sqlite3.IntegrityError):
            service.create_availability(101, 1, 1, 3)

        self.assertEqual(
            self.read_rows("SELECT COUNT(*) FROM EmployeeAvailability"),
            [(2,)],
        )

    def test_availability_rows_are_converted_to_calendar_events(self):
        service, _ = self.get_service()

        events = service.availability_db_to_events(
            service.get_employee_availability(101), 101
        )
        saved_event = next(event for event in events if event["id"] == 1)

        self.assertEqual(
            saved_event,
            {
                "id": 1,
                "title": "Morning Shift",
                "startTime": "08:00",
                "endTime": "12:00",
                "daysOfWeek": [2],
                "availability": 1,
                "color": "gray",
            },
        )
        self.assertIn(
            {
                "id": None,
                "title": "Morning Shift",
                "startTime": "08:00",
                "endTime": "12:00",
                "daysOfWeek": [0],
                "availability": 1,
                "color": "gray",
            },
            events,
        )

    def test_update_availability_creates_calendar_event_for_requested_day(self):
        service, _ = self.get_service()

        availability_id = service.update_availability(
            self.calendar_event(), employee_id=101
        )

        self.assertEqual(availability_id, 3)
        self.assertEqual(
            self.read_rows(
                """
                SELECT employee_id, shift_id, workday_id, availability
                FROM EmployeeAvailability WHERE employee_availability_id = ?
                """,
                (availability_id,),
            ),
            [(101, 1, 1, 0)],
        )

    def test_update_availability_updates_only_the_matching_record(self):
        service, _ = self.get_service()

        availability_id = service.update_availability(
            self.calendar_event(
                id="1",
                start="2026-11-24T08:00:00Z",
                end="2026-11-24T12:00:00Z",
                availability=2,
            ),
            employee_id=101,
        )

        self.assertEqual(availability_id, 1)
        self.assertEqual(
            self.read_rows(
                "SELECT availability FROM EmployeeAvailability "
                "WHERE employee_availability_id = 1"
            ),
            [(2,)],
        )

    def test_update_availability_reuses_existing_employee_shift_day_record(self):
        service, _ = self.get_service()

        availability_id = service.update_availability(
            self.calendar_event(
                start="2026-11-24T08:00:00Z",
                end="2026-11-24T12:00:00Z",
                availability=0,
            ),
            employee_id=101,
        )

        self.assertEqual(availability_id, 1)
        self.assertEqual(
            self.read_rows(
                "SELECT COUNT(*) FROM EmployeeAvailability "
                "WHERE employee_id = 101 AND shift_id = 1 AND workday_id = 2"
            ),
            [(1,)],
        )

    def test_is_employee_available_uses_workday_shift_and_availability(self):
        service, _ = self.get_service()

        self.assertTrue(service.is_employee_available(202, date(2026, 11, 24), 2))
        self.assertFalse(service.is_employee_available(101, date(2026, 11, 24), 1))
        self.assertFalse(service.is_employee_available(101, date(2026, 11, 24), 2))

    def test_update_availability_converts_utc_timestamps_to_local_workday(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "INSERT INTO Shifts (shift_id, shift_name, start_time, end_time) "
            "VALUES (?, ?, ?, ?)",
            (3, "Late Shift", "20:00", "23:00"),
        )
        connection.commit()
        connection.close()
        service, _ = self.get_service()

        availability_id = service.update_availability(
            self.calendar_event(
                shift_name="Late Shift",
                start="2026-11-23T01:00:00Z",
                end="2026-11-23T04:00:00Z",
                start_timezone_offset=300,
                end_timezone_offset=300,
            ),
            employee_id=101,
        )

        self.assertEqual(availability_id, 3)
        self.assertEqual(
            self.read_rows(
                "SELECT workday_id FROM EmployeeAvailability "
                "WHERE employee_availability_id = ?",
                (availability_id,),
            ),
            [(7,)],
        )

    def test_update_availability_returns_none_for_unknown_or_mismatched_record(self):
        service, _ = self.get_service()

        missing = service.update_availability(
            self.calendar_event(
                id=999,
                start="2026-11-24T08:00:00Z",
                end="2026-11-24T12:00:00Z",
            ),
            employee_id=101,
        )
        another_employee = service.update_availability(
            self.calendar_event(
                id=2,
                shift_name="Evening Shift",
                start="2026-11-24T16:00:00Z",
                end="2026-11-24T20:00:00Z",
            ),
            employee_id=101,
        )

        self.assertIsNone(missing)
        self.assertIsNone(another_employee)

    def test_update_availability_rejects_invalid_calendar_events(self):
        service, _ = self.get_service()
        invalid_events = (
            (None, "Request body must be a JSON object"),
            (self.calendar_event(start_timezone_offset=None), "timezone offset"),
            (self.calendar_event(start="not-a-date"), "must be an ISO datetime"),
            (self.calendar_event(start="2026-11-23T08:00:00"), "must include a timezone"),
            (self.calendar_event(availability=3), "Availability must be 0, 1, or 2"),
            (self.calendar_event(availability=True), "Availability must be 0, 1, or 2"),
            (self.calendar_event(shift_name="Unknown"), "Shift not found"),
            (self.calendar_event(id=1.5), "Availability ID must be a positive integer"),
            (self.calendar_event(id=0), "Availability ID must be a positive integer"),
        )

        for event, message in invalid_events:
            with self.subTest(event=event):
                with self.assertRaisesRegex(ValueError, message):
                    service.update_availability(event, employee_id=101)

    def test_repository_delete_removes_availability_and_its_shift(self):
        service, conn = self.get_service()

        self.assertTrue(service.availability_repository.delete_availability({"id": 1}))
        self.assertEqual(
            self.read_rows(
                "SELECT * FROM EmployeeAvailability WHERE employee_availability_id = 1"
            ),
            [],
        )
        self.assertEqual(self.read_rows("SELECT * FROM Shifts WHERE shift_id = 1"), [])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM Shifts").fetchone()[0], 1)

    def test_repository_delete_returns_false_for_unknown_record(self):
        service, _ = self.get_service()

        self.assertFalse(service.availability_repository.delete_availability({"id": 999}))

    def test_availability_page_renders_calendar_events_and_controls(self):
        self.login()

        response = self.client.get("/availability")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"title: 'Morning Shift'", response.data)
        self.assertIn(b"title: 'Evening Shift'", response.data)
        self.assertIn(b"startTime: '16:00'", response.data)
        self.assertIn(b"daysOfWeek: [2]", response.data)
        self.assertIn(b'id="eventTitle"', response.data)
        self.assertIn(b'id="eventTime"', response.data)
        self.assertIn(b'id="availableButton"', response.data)
        self.assertIn(b'id="busyButton"', response.data)

    def test_availability_route_creates_then_updates_calendar_event(self):
        self.login()

        created = self.client.post("/availability", json=self.calendar_event())

        self.assertEqual(created.status_code, 200)
        availability_id = created.get_json()["id"]
        self.assertEqual(availability_id, 3)

        updated = self.client.post(
            "/availability",
            json=self.calendar_event(id=availability_id, availability=2),
        )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["status"], "success")
        self.assertEqual(updated.get_json()["id"], availability_id)
        self.assertEqual(
            self.read_rows(
                "SELECT availability FROM EmployeeAvailability "
                "WHERE employee_availability_id = ?",
                (availability_id,),
            ),
            [(2,)],
        )

    def test_availability_route_rejects_invalid_events_and_other_employees(self):
        self.login()

        invalid = self.client.post(
            "/availability", json=self.calendar_event(availability=True)
        )
        other_employees_record = self.client.post(
            "/availability",
            json=self.calendar_event(
                id=2,
                shift_name="Evening Shift",
                start="2026-11-24T16:00:00Z",
                end="2026-11-24T20:00:00Z",
            ),
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["status"], "error")
        self.assertEqual(other_employees_record.status_code, 404)
        self.assertEqual(
            self.read_rows(
                "SELECT availability FROM EmployeeAvailability "
                "WHERE employee_availability_id = 2"
            ),
            [(0,)],
        )

    def test_routes_close_connections_after_success_redirect_and_error(self):
        self.login()
        connections = []

        def open_connection():
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            connections.append(conn)
            return conn

        with patch(
            "availability.AvailabilityRoutes.get_db_connection",
            side_effect=open_connection,
        ):
            self.assertEqual(self.client.get("/availability").status_code, 200)
            self.assertEqual(self.client.get("/avail_select").status_code, 302)
            self.assertEqual(
                self.client.post(
                    "/availability",
                    json=self.calendar_event(availability=True),
                ).status_code,
                400,
            )
            with patch.object(
                AvailabilityService,
                "get_employee_availability",
                side_effect=RuntimeError("test failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "test failure"):
                    self.client.get("/availability")
            with patch(
                "availability.AvailabilityRoutes._build_availability_service",
                side_effect=RuntimeError("construction failure"),
            ):
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

    def test_manager_availability_selector_lists_only_associates(self):
        self.login_manager()

        response = self.client.get("/avail_select")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"April Example (ID: 101)", response.data)
        self.assertNotIn(b"Bob Example (ID: 202)", response.data)
        self.assertIn(b"My Availability", response.data)

    def test_manager_selection_saves_employee_and_redirects(self):
        self.login_manager()

        response = self.client.post("/avail_select", data={"employee_id": "101"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/availability")
        with self.client.session_transaction() as session:
            self.assertEqual(session["availability_employee"], 101)

    def test_manager_can_select_own_availability(self):
        self.login_manager()

        response = self.client.post("/avail_select", data={"employee_id": "202"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/availability")
        with self.client.session_transaction() as session:
            self.assertEqual(session["availability_employee"], 202)

        self.assertEqual(self.client.get("/availability").status_code, 200)

        created = self.client.post(
            "/availability", json=self.calendar_event()
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(
            self.read_rows(
                "SELECT employee_id FROM EmployeeAvailability "
                "WHERE employee_availability_id = ?",
                (created.get_json()["id"],),
            ),
            [(202,)],
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

        response = self.client.post("/avail_select", data={"employee_id": "999"})

        self.assertEqual(response.status_code, 400)

    def test_administrator_can_select_any_employee_level(self):
        self.login_administrator()

        selector_response = self.client.get("/avail_select")
        self.assertEqual(selector_response.status_code, 200)
        self.assertIn(b"April Example (ID: 101)", selector_response.data)
        self.assertIn(b"Bob Example (ID: 202)", selector_response.data)

        response = self.client.post("/avail_select", data={"employee_id": "202"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/availability")
        with self.client.session_transaction() as session:
            self.assertEqual(session["availability_employee"], 202)


if __name__ == "__main__":
    unittest.main()
