import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from flask import template_rendered
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
                end_time TIME NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
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
            CREATE TABLE TimeOffRequests(
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                FOREIGN KEY (employee_id) REFERENCES Employees(employee_id)
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
            [(1, 101, 1, 2, 2), (2, 202, 2, 2, 1)],
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
            "availability": 1,
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

        availability_id = service.create_availability(101, 1, 1, 1)

        self.assertEqual(availability_id, 3)
        self.assertEqual(
            self.read_rows(
                """
                SELECT employee_id, shift_id, workday_id, availability
                FROM EmployeeAvailability WHERE employee_availability_id = ?
                """,
                (availability_id,),
            ),
            [(101, 1, 1, 1)],
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

    def test_repository_filters_availability_by_employee_and_finds_matches(self):
        service, conn = self.get_service()
        repository = service.availability_repository

        employee_rows = repository.get_availability_by_employee(101)
        self.assertEqual([row["employee_availability_id"] for row in employee_rows], [1])

        match = repository.get_matching_availability(101, 2, 1)
        self.assertEqual(match["employee_availability_id"], 1)
        self.assertIsNone(repository.get_matching_availability(101, 1, 1))

    def test_repository_returns_active_shifts_and_workdays_only(self):
        service, conn = self.get_service()
        repository = service.availability_repository

        conn.execute("UPDATE Shifts SET active = 0 WHERE shift_id = 1")
        conn.execute("UPDATE Workdays SET active = 0 WHERE workday_id = 2")
        conn.commit()

        self.assertEqual(
            [shift["shift_id"] for shift in repository.get_active_shifts()],
            [2],
        )
        self.assertEqual(
            repository.get_active_workdays(),
            [1, 3, 4, 5, 6, 7],
        )

    def test_saved_availability_groups_all_matching_days_for_one_shift(self):
        service, conn = self.get_service()

        conn.execute(
            "INSERT INTO EmployeeAvailability(employee_id, shift_id, workday_id, availability) "
            "VALUES (?, ?, ?, ?)",
            (101, 1, 3, 1),
        )
        conn.commit()

        value = service.availability_repository.get_days_with_matching_availability(
            1, 1, 2
        )
        available_days = service.availability_repository.get_days_with_matching_availability(
            1, 1, 1
        )

        self.assertEqual(value, "2")
        self.assertEqual(available_days, "3")

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

        events, _, _ = service.availability_db_to_events(
            service.get_employee_availability(101),
            [],
            101,
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
                "availability": 2,
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
                "availability": 2,
                "color": "gray",
            },
            events,
        )

    def test_calendar_keeps_each_saved_shift_on_its_own_workday(self):
        service, conn = self.get_service()
        conn.executemany(
            "INSERT INTO EmployeeAvailability(employee_id, shift_id, workday_id, availability) "
            "VALUES (101, 1, ?, 1)",
            [(1,), (3,), (7,)],
        )
        conn.execute(
            "INSERT INTO TimeOffRequests(employee_id, start_date, end_date, status) "
            "VALUES (101, '2026-11-23', '2026-11-29', 'Pending')"
        )
        conn.commit()
        events, _, _ = service.availability_db_to_events(
            service.get_employee_availability(101), service.get_time_off_by_employee(101), 101
        )
        saved = [event for event in events if event["id"] in (3, 4, 5)]
        self.assertEqual(
            [(event["id"], event["daysOfWeek"]) for event in saved],
            [(3, [1]), (4, [3]), (5, [0])],
        )
        for day in (0, 1, 3):
            self.assertEqual(sum(day in event["daysOfWeek"] for event in saved), 1)

    def test_time_off_is_converted_to_background_events_and_approved_days(self):
        service, _ = self.get_service()
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.executemany(
            """
            INSERT INTO TimeOffRequests(
                employee_id, start_date, end_date, status
            ) VALUES (?, ?, ?, ?)
            """,
            [
                (101, "2026-11-23", "2026-11-24", "Approved"),
                (101, "2026-11-25", "2026-11-25", "Pending"),
                (101, "2026-11-26", "2026-11-26", "Cancelled"),
                (101, "2026-11-27", "2026-11-27", "Viewed"),
            ],
        )
        connection.commit()
        connection.close()

        time_off = service.get_time_off_by_employee(101)
        _, background, approved_days = service.availability_db_to_events(
            [], time_off, 101
        )

        self.assertEqual(approved_days, ["2026-11-23", "2026-11-24"])
        self.assertEqual(
            [(item["title"], item["start"], item["end"], item["color"])
             for item in background],
            [
                ("Status: Approved", "2026-11-23", "2026-11-25", "red"),
                ("Status: Pending", "2026-11-25", "2026-11-26", "yellow"),
            ],
        )

    def test_create_time_off_request_persists_pending_background_event(self):
        self.login()
        start = date.today()
        end = start + timedelta(days=1)
        response = self.client.post(
            "/api/time-off-requests",
            json={"start_date": start.isoformat(), "end_date": end.isoformat(), "employee_id": 202},
        )

        self.assertEqual(response.status_code, 201)
        event = response.get_json()["event"]
        self.assertEqual(event, {
            "id": 1,
            "title": "Status: Pending",
            "start": start.isoformat(),
            "end": (end + timedelta(days=1)).isoformat(),
            "allDay": True,
            "display": "background",
            "color": "yellow",
        })
        expected_segments = [
            {**event, "end": end.isoformat()},
            {**event, "start": end.isoformat(), "title": ""},
        ]
        self.assertEqual(response.get_json()["background_events"], expected_segments)
        self.assertEqual(
            self.read_rows("SELECT employee_id, start_date, end_date, status FROM TimeOffRequests"),
            [(101, start.isoformat(), end.isoformat(), "Pending")],
        )
        service, _ = self.get_service()
        _, background, approved_days = service.availability_db_to_events(
            [], service.get_time_off_by_employee(101), 101
        )
        self.assertEqual(background, [event])
        self.assertEqual(approved_days, [])
        rendered = []
        def capture_template(sender, template, context, **extra):
            rendered.append(context)

        with template_rendered.connected_to(capture_template, app):
            page = self.client.get("/availability/101")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(rendered[0]["background"], expected_segments)

    def test_create_time_off_request_accepts_one_day(self):
        self.login()
        today = date.today()
        response = self.client.post(
            "/api/time-off-requests",
            json={"start_date": today.isoformat(), "end_date": today.isoformat()},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["event"]["end"], (today + timedelta(days=1)).isoformat())
        self.assertEqual(response.get_json()["background_events"], [response.get_json()["event"]])

    def test_split_background_event_preserves_segments_across_leap_day_and_year(self):
        for start, end, next_day in (
            ("2028-02-28", "2028-03-02", "2028-02-29"),
            ("2028-12-31", "2029-01-02", "2029-01-01"),
        ):
            with self.subTest(start=start):
                event = {
                    "id": 5, "title": "Status: Pending", "start": start, "end": end,
                    "allDay": True, "display": "background", "color": "yellow",
                }
                self.assertEqual(
                    AvailabilityService.split_background_event(event),
                    [
                        {**event, "end": next_day},
                        {**event, "start": next_day, "title": ""},
                    ],
                )

    def test_create_time_off_request_rejects_dates_before_today(self):
        self.login()
        today = date.today()
        yesterday = (today - timedelta(days=1)).isoformat()
        tomorrow = (today + timedelta(days=1)).isoformat()
        for start, end in (
            (yesterday, today.isoformat()),
            (yesterday, yesterday),
            (tomorrow, yesterday),
        ):
            with self.subTest(start=start, end=end):
                response = self.client.post(
                    "/api/time-off-requests",
                    json={"start_date": start, "end_date": end},
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json()["message"],
                    "Start Date and End Date must be today or later",
                )
        self.assertEqual(self.read_rows("SELECT * FROM TimeOffRequests"), [])

    def test_create_time_off_request_rejects_overlaps_for_non_cancelled_statuses(self):
        self.login()
        start = date.today() + timedelta(days=10)
        end = start + timedelta(days=2)
        for status in ("Pending", "Approved", "Denied", "Viewed"):
            connection = sqlite3.connect(self.database_path)
            connection.execute(
                "INSERT INTO TimeOffRequests(employee_id, start_date, end_date, status) "
                "VALUES (?, ?, ?, ?)",
                (101, start.isoformat() + "T08:00:00", end.isoformat() + "T17:00:00", status),
            )
            connection.commit()
            connection.close()
            for requested_start, requested_end in (
                (start, start),
                (end, end),
                (start + timedelta(days=1), start + timedelta(days=1)),
                (start - timedelta(days=1), end + timedelta(days=1)),
                (start - timedelta(days=1), start),
                (end, end + timedelta(days=1)),
            ):
                with self.subTest(status=status, start=requested_start, end=requested_end):
                    response = self.client.post(
                        "/api/time-off-requests",
                        json={
                            "start_date": requested_start.isoformat(),
                            "end_date": requested_end.isoformat(),
                        },
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.get_json()["message"], "Dates overlap an existing time-off request")
            connection = sqlite3.connect(self.database_path)
            connection.execute("DELETE FROM TimeOffRequests")
            connection.commit()
            connection.close()

    def test_time_off_overlap_is_employee_specific_and_adjacent_dates_are_allowed(self):
        self.login()
        today = date.today()
        start = today + timedelta(days=5)
        end = start + timedelta(days=2)
        connection = sqlite3.connect(self.database_path)
        connection.executemany(
            "INSERT INTO TimeOffRequests(employee_id, start_date, end_date, status) VALUES (?, ?, ?, ?)",
            [
                (101, start.isoformat(), end.isoformat(), "Pending"),
                (202, today.isoformat(), today.isoformat(), "Approved"),
            ],
        )
        connection.commit()
        connection.close()
        for day in (today, start - timedelta(days=1), end + timedelta(days=1)):
            with self.subTest(day=day):
                response = self.client.post(
                    "/api/time-off-requests",
                    json={"start_date": day.isoformat(), "end_date": day.isoformat()},
                )
                self.assertEqual(response.status_code, 201)

    def test_time_off_modal_receives_all_existing_ranges(self):
        self.login()
        connection = sqlite3.connect(self.database_path)
        connection.executemany(
            "INSERT INTO TimeOffRequests(employee_id, start_date, end_date, status) VALUES (?, ?, ?, ?)",
            [
                (101, "2035-01-02T08:00:00", "2035-01-03T17:00:00", "Cancelled"),
                (101, "2035-02-01", "2035-02-02", "Denied"),
                (202, "2035-03-01", "2035-03-02", "Approved"),
            ],
        )
        connection.commit()
        connection.close()
        rendered = []

        def capture_template(sender, template, context, **extra):
            rendered.append(context)

        with template_rendered.connected_to(capture_template, app):
            response = self.client.get("/availability/101")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(rendered[0]["time_off_ranges"], [
            {"start": "2035-02-01", "end": "2035-02-02"},
        ])

    def test_time_off_request_can_overlap_cancelled_dates(self):
        self.login()
        start = date.today() + timedelta(days=10)
        end = start + timedelta(days=2)
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "INSERT INTO TimeOffRequests(employee_id, start_date, end_date, status) "
            "VALUES (?, ?, ?, ?)",
            (101, start.isoformat(), end.isoformat(), "Cancelled"),
        )
        connection.commit()
        connection.close()
        response = self.client.post(
            "/api/time-off-requests",
            json={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            self.read_rows("SELECT status FROM TimeOffRequests ORDER BY request_id"),
            [("Cancelled",), ("Pending",)],
        )

    def test_manager_review_returns_request_details(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "INSERT INTO TimeOffRequests(employee_id, start_date, end_date, status) "
            "VALUES (101, '2026-11-23', '2026-12-07', 'Pending')"
        )
        connection.commit()
        connection.close()
        self.login_manager()
        with self.client.session_transaction() as session_data:
            session_data["availability_employee"] = 101
        response = self.client.get("/api/time-off-requests/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["request"], {
            "id": 1, "employee_name": "April Example", "start_date": "2026-11-23",
            "end_date": "2026-12-07", "status": "Pending",
        })

    def test_review_approve_and_deny_pending_requests(self):
        connection = sqlite3.connect(self.database_path)
        connection.executemany(
            "INSERT INTO TimeOffRequests(employee_id, start_date, end_date, status) "
            "VALUES (101, ?, ?, 'Pending')",
            [("2026-11-23", "2026-11-24"), ("2026-12-01", "2026-12-01")],
        )
        connection.commit()
        connection.close()
        self.login_administrator()
        with self.client.session_transaction() as session_data:
            session_data["availability_employee"] = 101
        approved = self.client.put("/api/time-off-requests/1", json={"status": "Approved"})
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.get_json()["approved_days"], ["2026-11-23", "2026-11-24"])
        self.assertEqual(approved.get_json()["background_events"][0]["color"], "red")
        denied = self.client.put("/api/time-off-requests/2", json={"status": "Denied"})
        self.assertEqual(denied.status_code, 200)
        self.assertEqual(denied.get_json()["background_events"][0]["color"], "gray")
        self.assertEqual(
            self.read_rows("SELECT status FROM TimeOffRequests ORDER BY request_id"),
            [("Approved",), ("Denied",)],
        )
        stale = self.client.put("/api/time-off-requests/1", json={"status": "Denied"})
        self.assertEqual(stale.status_code, 409)

    def test_review_permissions_invalid_status_and_employee_scope(self):
        connection = sqlite3.connect(self.database_path)
        connection.executemany(
            "INSERT INTO TimeOffRequests(employee_id, start_date, end_date, status) VALUES (?, ?, ?, ?)",
            [(101, "2026-11-23", "2026-11-23", "Pending"),
             (202, "2026-11-23", "2026-11-23", "Pending"),
             (101, "2026-11-24", "2026-11-24", "Denied")],
        )
        connection.commit()
        connection.close()
        self.assertEqual(self.client.get("/api/time-off-requests/1").status_code, 302)
        self.login()
        self.assertEqual(self.client.put("/api/time-off-requests/1", json={"status": "Approved"}).status_code, 403)
        self.client.get("/logout")
        self.login_manager()
        self.assertEqual(self.client.get("/api/time-off-requests/2").status_code, 403)
        with self.client.session_transaction() as session_data:
            session_data["availability_employee"] = 101
        self.assertEqual(self.client.get("/api/time-off-requests/2").status_code, 404)
        self.assertEqual(self.client.get("/api/time-off-requests/3").status_code, 409)
        for data in ({}, {"status": "Cancelled"}, None):
            self.assertEqual(self.client.put("/api/time-off-requests/1", json=data).status_code, 400)
        self.assertEqual(
            self.read_rows("SELECT status FROM TimeOffRequests ORDER BY request_id"),
            [("Pending",), ("Pending",), ("Denied",)],
        )

    def test_review_controls_only_for_other_employees_pending_requests(self):
        connection = sqlite3.connect(self.database_path)
        connection.executemany(
            "INSERT INTO TimeOffRequests(employee_id, start_date, end_date, status) VALUES (101, ?, ?, ?)",
            [("2026-11-23", "2026-11-24", "Pending"), ("2026-11-25", "2026-11-25", "Denied")],
        )
        connection.commit()
        connection.close()
        self.login_manager()
        self.assertNotIn(b'id="reviewTimeOffModal"', self.client.get("/availability/202").data)
        contexts = []

        def capture_template(sender, template, context, **extra):
            contexts.append(context)

        with template_rendered.connected_to(capture_template, app):
            response = self.client.get("/availability/101")
        self.assertIn(b'id="reviewTimeOffModal"', response.data)
        self.assertNotIn(b"Review pending time off", response.data)
        self.assertTrue(all(
            segment.get("reviewRequestId") == 1
            for segment in contexts[0]["background"] if segment["id"] == 1
        ))
        self.assertTrue(all(
            "reviewRequestId" not in segment
            for segment in contexts[0]["background"] if segment["id"] == 2
        ))

    def test_create_time_off_request_rejects_invalid_dates(self):
        self.login()
        for data in (
            None,
            [],
            {},
            {"start_date": "2026-02-30", "end_date": "2026-03-01"},
            {"start_date": "20261123", "end_date": "2026-11-24"},
            {"start_date": "2026-11-25", "end_date": "2026-11-24"},
            {"start_date": "9999-12-31", "end_date": "9999-12-31"},
        ):
            with self.subTest(data=data):
                response = self.client.post("/api/time-off-requests", json=data)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["status"], "error")
        self.assertEqual(self.read_rows("SELECT * FROM TimeOffRequests"), [])

    def test_time_off_button_is_visible_on_own_availability(self):
        for login in (self.login, self.login_manager, self.login_administrator):
            with self.subTest(login=login.__name__):
                login()
                if login == self.login:
                    response = self.client.get("/availability/101")
                elif login == self.login_manager:
                    response = self.client.get("/availability/202")
                else:
                    response = self.client.get("/availability/303")
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'id="newTimeOffButton"', response.data)
                self.assertIn(b'id="timeOffModal"', response.data)
                self.client.get("/logout")

    def test_time_off_button_is_hidden_on_another_employees_availability(self):
        for login in (self.login_manager, self.login_administrator):
            with self.subTest(login=login.__name__):
                login()
                response = self.client.get("/availability/101")
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(b'id="newTimeOffButton"', response.data)
                self.assertNotIn(b'id="timeOffModal"', response.data)
                self.assertIn(b'id="calendar"', response.data)
                self.client.get("/logout")

    def test_create_time_off_request_uses_current_user_for_submission(self):
        self.login_manager()
        response = self.client.post(
            "/api/time-off-requests",
            json={"start_date": date.today().isoformat(), "end_date": date.today().isoformat()},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.read_rows("SELECT employee_id FROM TimeOffRequests"), [(202,)])

    def test_create_time_off_request_requires_login(self):
        response = self.client.post(
            "/api/time-off-requests",
            json={"start_date": "2026-11-23", "end_date": "2026-11-23"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.read_rows("SELECT * FROM TimeOffRequests"), [])

    def test_time_off_repository_filters_by_employee_and_preserves_all_statuses(self):
        service, _ = self.get_service()
        connection = sqlite3.connect(self.database_path)
        connection.executemany(
            """
            INSERT INTO TimeOffRequests(
                employee_id, start_date, end_date, status
            ) VALUES (?, ?, ?, ?)
            """,
            [
                (101, "2026-11-23", "2026-11-23", "Approved"),
                (101, "2026-11-24", "2026-11-24", "Denied"),
                (202, "2026-11-25", "2026-11-25", "Pending"),
            ],
        )
        connection.commit()
        connection.close()

        rows = service.get_time_off_by_employee(101)

        self.assertEqual(
            [(row["employee_id"], row["status"]) for row in rows],
            [(101, "Approved"), (101, "Denied")],
        )

    def test_denied_time_off_is_rendered_as_gray_background(self):
        service, _ = self.get_service()
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            """
            INSERT INTO TimeOffRequests(
                employee_id, start_date, end_date, status
            ) VALUES (?, ?, ?, ?)
            """,
            (101, "2026-11-24", "2026-11-25", "Denied"),
        )
        connection.commit()
        connection.close()

        time_off = service.get_time_off_by_employee(101)
        _, background, approved_days = service.availability_db_to_events(
            [], time_off, 101
        )

        self.assertEqual(approved_days, [])
        self.assertEqual(
            [(item["title"], item["start"], item["end"], item["color"])
             for item in background],
            [("Status: Denied", "2026-11-24", "2026-11-26", "gray")],
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
            [(101, 1, 1, 1)],
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

        self.assertTrue(service.is_employee_available(202, 2, 2))
        self.assertFalse(service.is_employee_available(101, 2, 1))
        self.assertFalse(service.is_employee_available(101, 2, 2))

        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "UPDATE EmployeeAvailability SET availability = 0 "
            "WHERE employee_id = 202 AND workday_id = 2 AND shift_id = 2"
        )
        connection.commit()
        connection.close()
        self.assertFalse(service.is_employee_available(202, 2, 2))

        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "UPDATE EmployeeAvailability SET availability = 2 "
            "WHERE employee_id = 202 AND workday_id = 2 AND shift_id = 2"
        )
        connection.commit()
        connection.close()
        self.assertFalse(service.is_employee_available(202, 2, 2))

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

    def test_repository_delete_validates_request_body_and_id(self):
        service, _ = self.get_service()

        with self.assertRaisesRegex(ValueError, "JSON object"):
            service.availability_repository.delete_availability(None)
        with self.assertRaisesRegex(ValueError, "AvailabilityID is required"):
            service.availability_repository.delete_availability({})

    def test_repository_delete_keeps_shift_used_by_another_availability(self):
        service, _ = self.get_service()
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "INSERT INTO EmployeeAvailability(employee_id, shift_id, workday_id, availability) "
            "VALUES (?, ?, ?, ?)",
            (202, 1, 3, 1),
        )
        connection.commit()
        connection.close()

        repository = service.availability_repository

        self.assertTrue(repository.delete_availability({"id": 1}))
        self.assertEqual(
            self.read_rows("SELECT shift_id FROM Shifts WHERE shift_id = 1"),
            [(1,)],
        )
        self.assertEqual(
            self.read_rows(
                "SELECT COUNT(*) FROM EmployeeAvailability WHERE shift_id = 1"
            ),
            [(1,)],
        )

    def test_availability_page_renders_calendar_events_and_controls(self):
        self.login()

        response = self.client.get("/availability/101")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"title": "Morning Shift"', response.data)
        self.assertIn(b'"title": "Evening Shift"', response.data)
        self.assertIn(b'"startTime": "16:00"', response.data)
        self.assertIn(b'"daysOfWeek": [2]', response.data)
        self.assertIn(b'id="eventTitle"', response.data)
        self.assertIn(b'id="eventTime"', response.data)
        self.assertIn(b'id="availableButton"', response.data)
        self.assertIn(b'id="busyButton"', response.data)

    def test_availability_route_creates_then_updates_calendar_event(self):
        self.login()

        created = self.client.post("/availability/101", json=self.calendar_event())

        self.assertEqual(created.status_code, 200)
        availability_id = created.get_json()["id"]
        self.assertEqual(availability_id, 3)

        updated = self.client.post(
            "/availability/101",
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
            "/availability/101", json=self.calendar_event(availability=True)
        )
        other_employees_record = self.client.post(
            "/availability/202",
            json=self.calendar_event(
                id=2,
                shift_name="Evening Shift",
                start="2026-11-24T16:00:00Z",
                end="2026-11-24T20:00:00Z",
            ),
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["status"], "error")
        self.assertEqual(other_employees_record.status_code, 403)
        self.assertEqual(
            self.read_rows(
                "SELECT availability FROM EmployeeAvailability "
                "WHERE employee_availability_id = 2"
            ),
            [(1,)],
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
            self.assertEqual(self.client.get("/availability/101").status_code, 200)
            self.assertEqual(self.client.get("/availability").status_code, 302)
            self.assertEqual(
                self.client.post(
                    "/availability/101",
                    json=self.calendar_event(availability=True),
                ).status_code,
                400,
            )
            with patch.object(
                AvailabilityService,
                "get_availability_by_employee",
                side_effect=RuntimeError("test failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "test failure"):
                    self.client.get("/availability/101")
            with patch(
                "availability.AvailabilityRoutes._build_availability_service",
                side_effect=RuntimeError("construction failure"),
            ):
                for url in ("/availability/101", "/availability"):
                    with self.subTest(url=url):
                        with self.assertRaisesRegex(RuntimeError, "construction failure"):
                            self.client.get(url)

        self.assertEqual(len(connections), 6)
        for conn in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")

    def test_associate_availability_selector_redirects_to_own_availability(self):
        self.login()

        response = self.client.get("/availability")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/availability/101")

    def test_manager_availability_selector_lists_only_associates(self):
        self.login_manager()

        response = self.client.get("/availability")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"April Example (ID: 101)", response.data)
        self.assertNotIn(b"Bob Example (ID: 202)", response.data)
        self.assertIn(b"My Availability", response.data)

    def test_manager_selection_redirects_to_employee_detail(self):
        self.login_manager()

        response = self.client.get("/availability/101")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"April Example", response.data)

    def test_manager_can_view_own_availability(self):
        self.login_manager()

        response = self.client.get("/availability/202")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Bob Example", response.data)

        created = self.client.post(
            "/availability/202", json=self.calendar_event()
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

    def test_manager_cannot_view_unknown_employee_availability(self):
        self.login_manager()

        response = self.client.get("/availability/999")

        self.assertEqual(response.status_code, 403)

    def test_manager_cannot_view_other_manager_availability(self):
        self.login_manager()

        response = self.client.post("/availability/202")

        self.assertEqual(response.status_code, 404)

    def test_manager_cannot_select_an_unknown_employee(self):
        self.login_manager()

        response = self.client.get("/availability/999")

        self.assertEqual(response.status_code, 403)

    def test_administrator_can_view_any_employee(self):
        self.login_administrator()

        selector_response = self.client.get("/availability")
        self.assertEqual(selector_response.status_code, 200)
        self.assertIn(b"April Example (ID: 101)", selector_response.data)
        self.assertIn(b"Bob Example (ID: 202)", selector_response.data)

        response = self.client.get("/availability/202")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Bob Example", response.data)


if __name__ == "__main__":
    unittest.main()
