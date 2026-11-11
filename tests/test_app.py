import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash



import app as app_module
from app import app

# To run:
# Navigate to the project root directory and run:
# python -m unittest discover -s tests -p "test_*.py"


class WorkforceIQTestCase(unittest.TestCase):
    def setUp(self):
        # Makes temp directory, gets path to it
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_directory.name, "testing.db")

        # Set app to testing mode, and override the database path to the temp database
        app.config.update(TESTING=True, DATABASE=self.database_path)
        self.create_test_database()
        self.client = app.test_client()

    def tearDown(self):
        # Ends testing mode, resets database path to default, and cleans up temp directory
        app.config["TESTING"] = False
        app.config["DATABASE"] = os.path.join("database", "workforce.db")
        self.temp_directory.cleanup()

    def create_test_database(self):
        """Builds the same tables as database/init_db.py, with sample rows."""
        connection = sqlite3.connect(self.database_path)

        connection.executescript("""
            CREATE TABLE SystemRoles(
                system_role_id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL UNIQUE,
                description TEXT
            );

            CREATE TABLE Roles(
                role_id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL UNIQUE,
                system_role_id INTEGER NOT NULL,
                FOREIGN KEY (system_role_id) REFERENCES SystemRoles(system_role_id)
            );

            CREATE TABLE Employees(
                employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                hourly_rate REAL NOT NULL,
                FOREIGN KEY (role_id) REFERENCES Roles(role_id)
            );

            CREATE TABLE Users(
                userid INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                system_role_id INTEGER NOT NULL DEFAULT 0,
                employee_id INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (system_role_id) REFERENCES SystemRoles(system_role_id),
                FOREIGN KEY (employee_id) REFERENCES Employees(employee_id)
            );

            CREATE TABLE DemandHistory(
                demand_id INTEGER PRIMARY KEY AUTOINCREMENT,
                demand_date TEXT NOT NULL,
                sales_amount REAL NOT NULL
            );

            CREATE TABLE Forecasts(
                forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_date TEXT NOT NULL UNIQUE,
                projected_sales REAL NOT NULL,
                projected_sales_low REAL NOT NULL,
                projected_sales_high REAL NOT NULL,
                required_labor_hours REAL,
                labor_budget REAL NOT NULL
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
                availability INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (employee_id) REFERENCES Employees(employee_id),
                FOREIGN KEY (shift_id) REFERENCES Shifts(shift_id)
            );
        """)

        connection.executemany(
            "INSERT INTO SystemRoles(system_role_id, role_name, description) VALUES (?, ?, ?)",
            [
                (0, "Unregistered", "No access"),
                (1, "Associate", "Limited access"),
                (2, "Manager", "Can manage employees"),
                (3, "Administrator", "Full access"),
            ],
        )
        connection.executemany(
            "INSERT INTO Roles(role_name, system_role_id) VALUES (?, ?)",
            [("Manager", 2), ("Associate", 1)],
        )
        connection.executemany(
            "INSERT INTO Employees(role_id, first_name, last_name, hourly_rate) VALUES (?, ?, ?, ?)",
            [
                (1, "Alice", "Example", 30.0),
                (2, "Bob", "Example", 20.0),
                (2, "Carol", "Example", 22.5),
            ],
        )

        connection.executemany(
        """
        INSERT INTO DemandHistory
        (demand_date, sales_amount)
        VALUES (?, ?)
        """,
        [
            ("2026-11-01", 4500),
            ("2026-11-02", 4700),
            ("2026-11-03", 6200),
            ("2026-11-04", 5900),
            ("2026-11-05", 4600),
            ("2026-11-06", 4550),
            ("2026-11-07", 4800),
        ]
    )

        # The "test" login belongs to Bob (an Associate)
        connection.execute(
            "INSERT INTO Users(username, password, system_role_id, employee_id) VALUES (?, ?, ?, ?)",
            ("test", generate_password_hash("password123"), 1, 2),
        )
        connection.execute(
            "INSERT INTO Shifts(shift_name, start_time, end_time) VALUES (?, ?, ?)",
            ("Test Shift", "2026-11-10T08:00:00", "2026-11-10T12:00:00"),
        )
        connection.execute(
            "INSERT INTO EmployeeAvailability(employee_id, shift_id, availability) VALUES (?, ?, ?)",
            (2, 1, 1),
        )

        connection.commit()
        connection.close()

    def login_as_test_user(self):
        return self.client.post(
            "/login",
            data={"username": "test", "password": "password123"},
            follow_redirects=False,
        )

    # Tests (run after setUp and before tearDown)

    # Checks get_db_connection returns a connection to the correct database
    def test_get_db_connection_returns_correct_database(self):
        expected_connection = sqlite3.connect(self.database_path)
        expected_cursor = expected_connection.cursor()
        expected_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Users'"
        )
        expected_result = expected_cursor.fetchone()
        expected_connection.close()

        with app.app_context():
            actual_connection = app_module.get_db_connection()
        actual_cursor = actual_connection.cursor()
        actual_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Users'"
        )
        actual_result = actual_cursor.fetchone()
        actual_connection.close()

        self.assertEqual(expected_result[0], actual_result["name"])

    # Checks that the string from get_employee_context contains the correct data.
    # (get_employees_json() no longer exists, so requests.get is mocked directly.)
    @unittest.skip("Moved to AssistantService tests")
    def test_get_employee_context_string(self):
        preset_employees = [
            {"first_name": "Alice", "last_name": "Example", "role": "Manager", "hourly_rate": 30.0},
            {"first_name": "Bob", "last_name": "Example", "role": "Associate", "hourly_rate": 20.0},
            {"first_name": "Carol", "last_name": "Example", "role": "Associate", "hourly_rate": 22.5},
        ]

        with patch.object(app_module.requests, "get") as mock_get:
            mock_get.return_value.json.return_value = preset_employees
            context = app_module.get_employee_context()

        self.assertIn("Name: Alice Example, Role: Manager, Wage: $30.0/hr", context)
        self.assertIn("Name: Bob Example, Role: Associate, Wage: $20.0/hr", context)
        self.assertIn("Name: Carol Example, Role: Associate, Wage: $22.5/hr", context)

    def test_forecast_module_generates_14_day_forecast(self):

        from database.connection import get_db_connection
        from forecasting.ForecastRepository import ForecastRepository
        from forecasting.ForecastService import ForecastService

        with app.app_context():
            connection = app_module.get_db_connection()

        try:
            repository = ForecastRepository(connection)
            service = ForecastService(repository)

            forecasts = service.generate_two_week_forecast()

            self.assertEqual(len(forecasts), 14)

        finally:
            connection.close()

    # TODO: expand into more tests
    @unittest.skip("Moved to AssistantService tests")
    def test_ask_ollama_returns_expected_response(self):
        expected_response = "Alice Example's role is Manager."

        with patch.object(app_module.requests, "post") as mock_post:
            mock_post.return_value.json.return_value = {"response": expected_response}
            actual_response = app_module.ask_ollama("What is Alice Example's role?")

        self.assertEqual(actual_response, expected_response)

    # TODO: test ai_assistant() for hallucination

    # Check that the login page loads successfully
    def test_login_page_loads(self):
        response = self.client.get("/login")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)

    # Check that the test profile can log in successfully
    def test_test_profile_can_log_in(self):
        response = self.login_as_test_user()

        print(response.data.decode())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/dashboard")

    def test_availability_calendar_renders_database_events(self):
        self.login_as_test_user()

        response = self.client.get("/availability")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"title: 'Test Shift'", response.data)
        self.assertIn(b"start: '2026-11-10T08:00:00'", response.data)
        self.assertIn(b'<form method="dialog">', response.data)
        self.assertIn(b'id="closeModalBtn" type="submit"', response.data)
        self.assertIn(b'id="modalTitle" type="text"', response.data)
        self.assertIn(b'id="modalStart" type="datetime-local"', response.data)
        self.assertIn(b'id="modalEnd" type="datetime-local"', response.data)
        self.assertIn(b'id="modalAvailable" type="checkbox"', response.data)
        self.assertIn(b'dateClick: function(info)', response.data)
        self.assertIn(b'openCreateEventModal(info.date)', response.data)

    def test_availability_updates_accept_calendar_callback_payloads(self):
        callback_payloads = [
            {
                "id": 1,
                "start": "2026-11-10T09:00:00",
                "end": "2026-11-10T13:00:00",
            },
            {
                "id": 1,
                "start": "2026-11-10T10:00:00",
                "end": "2026-11-10T14:00:00",
            },
            {
                "id": 1,
                "title": "Updated Test Shift",
                "start": "2026-11-10T11:00:00",
                "end": "2026-11-10T15:00:00",
                "availability": 0,
            },
        ]

        for payload in callback_payloads:
            with self.subTest(payload=payload):
                response = self.client.post("/availability", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["status"], "success")

        connection = sqlite3.connect(self.database_path)
        shift = connection.execute(
            "SELECT shift_name, start_time, end_time FROM Shifts WHERE shift_id = 1"
        ).fetchone()
        availability = connection.execute(
            "SELECT availability FROM EmployeeAvailability WHERE employee_availability_id = 1"
        ).fetchone()[0]
        connection.close()

        self.assertEqual(
            shift,
            ("Updated Test Shift", "2026-11-10T11:00:00", "2026-11-10T15:00:00"),
        )
        self.assertEqual(availability, 0)

    def test_availability_can_be_created_for_logged_in_employee(self):
        self.login_as_test_user()

        response = self.client.post(
            "/availability",
            json={
                "title": "New Shift",
                "start": "2026-11-11T09:00:00",
                "end": "2026-11-11T10:00:00",
                "availability": 1,
            },
        )

        self.assertEqual(response.status_code, 201)
        created_id = response.get_json()["id"]
        connection = sqlite3.connect(self.database_path)
        created = connection.execute(
            """
            SELECT s.shift_name, s.start_time, s.end_time, ea.availability, ea.employee_id
            FROM EmployeeAvailability ea
            JOIN Shifts s ON s.shift_id = ea.shift_id
            WHERE ea.employee_availability_id = ?
            """,
            (created_id,),
        ).fetchone()
        connection.close()

        self.assertEqual(
            created,
            ("New Shift", "2026-11-11T09:00:00", "2026-11-11T10:00:00", 1, 2),
        )

    # Check that invalid credentials are rejected
    def test_invalid_credentials_are_rejected(self):
        response = self.client.post(
            "/login",
            data={"username": "test", "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password.", response.data)

    # Check that pages other than login/register send signed-out users to /login
    def test_pages_require_login(self):
        for path in ("/dashboard", "/employees", "/forecast", "/ai"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, msg=path)
            self.assertIn("/login", response.location, msg=path)

    def test_registration_creates_user_and_employee(self):
        response = self.client.post(
            "/register",
            data={
                "username": "newuser",
                "password": "password123",
                "first_name": "Robbie",
                "last_name": "Example",
                "job_title": "Shift Supervisor",
                "level": "Manager",
                "hourly_rate": "28.50",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/dashboard")

        connection = sqlite3.connect(self.database_path)
        user = connection.execute(
            "SELECT userid, system_role_id FROM Users WHERE username = ?",
            ("newuser",),
        ).fetchone()
        employee = connection.execute(
            """
            SELECT Employees.first_name, Employees.last_name,
                   Roles.role_name, Employees.hourly_rate
            FROM Users
            JOIN Employees ON Employees.employee_id = Users.employee_id
            JOIN Roles ON Roles.role_id = Employees.role_id
            WHERE Users.userid = ?
            """,
            (user[0],),
        ).fetchone()
        connection.close()

        self.assertEqual(user[1], 2)  # "Manager" is system role 2
        self.assertEqual(employee, ("Robbie", "Example", "Shift Supervisor", 28.5))

    def test_registration_rejects_invalid_fields(self):
        response = self.client.post(
            "/register",
            data={
                "username": "",
                "password": "",
                "first_name": "Dana2",
                "last_name": "3Example",
                "job_title": "",
                "level": "Associate",
                "hourly_rate": "12.345",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Username is required.", response.data)
        self.assertIn(b"Password is required.", response.data)
        self.assertIn(b"First name must not contain numbers.", response.data)
        self.assertIn(b"Last name must not contain numbers.", response.data)
        self.assertIn(b"Job title is required.", response.data)
        self.assertIn(b"no more than 2 digits", response.data)

    def test_registration_rejects_duplicate_username(self):
        response = self.client.post(
            "/register",
            data={
                "username": "test",  # already exists in create_test_database
                "password": "password123",
                "first_name": "Robbie",
                "last_name": "Example",
                "job_title": "Cashier",
                "level": "Associate",
                "hourly_rate": "15.00",
            },
        )

        self.assertEqual(response.status_code, 400)

        # The failed registration must not leave a half-created employee behind
        connection = sqlite3.connect(self.database_path)
        count = connection.execute(
            "SELECT COUNT(*) FROM Employees WHERE first_name = ?", ("Robbie",)
        ).fetchone()[0]
        connection.close()
        self.assertEqual(count, 0)

    # Check that the employee API returns the pre-set data from create_test_database
    def test_employee_api_returns_pre_set_data(self):
        response = self.client.get("/api/employees")

        self.assertEqual(response.status_code, 200)
        employees = response.get_json()
        self.assertEqual(len(employees), 3)
        self.assertEqual(employees[0]["first_name"], "Alice")
        self.assertEqual(employees[0]["last_name"], "Example")
        self.assertAlmostEqual(employees[1]["hourly_rate"], 20.0)
        self.assertEqual(employees[2]["role"], "Associate")

    def test_employee_can_be_added_to_testing_database(self):
        self.login_as_test_user()  # /add_employee and /employees require login

        response = self.client.post(
            "/add_employee",
            data={
                "first_name": "Dana",
                "last_name": "Example",
                "role_name": "Supervisor",
                "level": "2",
                "wage": "28.0",
                "username": "test",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)  # Check that the response is a redirect

        connection = sqlite3.connect(self.database_path)
        dana_example = connection.execute(
            """
            SELECT Employees.first_name, Employees.last_name,
                   Roles.role_name, Employees.hourly_rate, Employees.employee_id
            FROM Employees
            JOIN Roles ON Roles.role_id = Employees.role_id
            WHERE Employees.first_name = ?
            """,
            ("Dana",),
        ).fetchone()
        linked_employee_id = connection.execute(
            "SELECT employee_id FROM Users WHERE username = ?", ("test",)
        ).fetchone()[0]
        connection.close()

        self.assertEqual(dana_example[:4], ("Dana", "Example", "Supervisor", 28.0))
        # The "test" login is now linked to the new employee record
        self.assertEqual(linked_employee_id, dana_example[4])

        response = self.client.get("/employees")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Associate", response.data)

    def test_forecast_page_loads_for_authenticated_user(self):
        """
        Verify that the forecast page renders
        for authenticated users.
        """

        self.login_as_test_user()

        response = self.client.get("/forecast")

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            b"Two-Week Staffing Forecast",
            response.data
        )

    def test_forecast_page_contains_labor_budget(self):
        """
        Verify that labor budget information
        is displayed on the forecast page.
        """

        self.login_as_test_user()

        response = self.client.get("/forecast")

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            b"Projected Labor Budget",
            response.data
        )
    
if __name__ == "__main__":
    unittest.main()