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
        #Makes temp directory, gets path to it
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_directory.name, "testing.db")

        #Set app to testing mode, and override the database path to the temp database
        app.config.update(TESTING=True, DATABASE=self.database_path)
        self.create_test_database()
        self.client = app.test_client()

    def tearDown(self):
        #Ends testing mode, resets database path to default, and cleans up temp directory
        app.config["TESTING"] = False
        app.config["DATABASE"] = os.path.join("database", "workforce.db")
        self.temp_directory.cleanup()

    def create_test_database(self):
        connection = sqlite3.connect(self.database_path)

        connection.executescript("""
            CREATE TABLE Users(
                userid INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            );

            CREATE TABLE employees(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                wage REAL NOT NULL
            );
        """)

        connection.execute(
            "INSERT INTO Users(username, password) VALUES (?, ?)",
            ("test", generate_password_hash("password123")),
        )
        connection.executemany(
            "INSERT INTO employees(name, role, wage) VALUES (?, ?, ?)",
            [
                ("Alice Example", "Manager", 30.0),
                ("Bob Example", "Associate", 20.0),
                ("Carol Example", "Associate", 22.5),
            ],
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

        actual_connection = app_module.get_db_connection()
        actual_cursor = actual_connection.cursor()
        actual_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Users'"
        )
        actual_result = actual_cursor.fetchone()
        actual_connection.close()

        self.assertEqual(expected_result[0], actual_result["name"])

    def test_get_employees_json(self):
        preset_employees = [
            {"name": "Alice Example", "role": "Manager", "wage": 30.0},
            {"name": "Bob Example", "role": "Associate", "wage": 20.0},
            {"name": "Carol Example", "role": "Associate", "wage": 22.5},
        ]

        # Mock version of requests.get to return preset_employees when called
        with patch.object(app_module.requests, "get") as mock_get:
            # Get both sets of employees as json
            mock_get.return_value.json.return_value = preset_employees
            employees_json = app_module.get_employees_json()

        self.assertEqual(employees_json, preset_employees)

    # Checks that the string from get_employee_context contains the correct data
    def test_get_employee_context_string(self):
        preset_employees = [
            {"name": "Alice Example", "role": "Manager", "wage": 30.0},
            {"name": "Bob Example", "role": "Associate", "wage": 20.0},
            {"name": "Carol Example", "role": "Associate", "wage": 22.5},
        ]

        with patch.object(app_module.requests, "get") as mock_get:
            mock_get.return_value.json.return_value = preset_employees
            context = app_module.get_employee_context()

        self.assertIn("Name: Alice Example, Role: Manager, Wage: $30.0/hr", context)
        self.assertIn("Name: Bob Example, Role: Associate, Wage: $20.0/hr", context)
        self.assertIn("Name: Carol Example, Role: Associate, Wage: $22.5/hr", context)

    # TODO: redo this once we have real forcasting module
    def test_generate_forecast_returns_expected_value(self):
        # Based on static data, should be calculated for real tests
        expected_forecast = 200
        actual_forecast = app_module.generate_forecast()
        self.assertEqual(actual_forecast, expected_forecast)

    # TODO: expand into more tests
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

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/dashboard")

    # Check that invalid credentials are rejected
    def test_invalid_credentials_are_rejected(self):
        response = self.client.post(
            "/login",
            data={"username": "test", "password": "incorrect"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password.", response.data)

    # Check that the employee API returns the pre-set data from create_test_database
    def test_employee_api_returns_pre_set_data(self):
        response = self.client.get("/api/employees")

        self.assertEqual(response.status_code, 200)
        employees = response.get_json()
        self.assertEqual(len(employees), 3)
        self.assertEqual(employees[0]["name"], "Alice Example")
        self.assertAlmostEqual(employees[1]["wage"], 20.0)
        self.assertEqual(employees[2]["role"], "Associate")


    def test_employee_can_be_added_to_testing_database(self):
        response = self.client.post(
            "/add_employee",
            data={
                "name": "Dana Example",
                "role": "Supervisor",
                "wage": "28.0",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302) # Check that the response is a redirect

        connection = sqlite3.connect(self.database_path)
        dana_example = connection.execute(
            "SELECT name, role, wage FROM employees WHERE name = ?",
            ("Dana Example",),
        ).fetchone()
        connection.close()

        self.assertEqual(dana_example, ("Dana Example", "Supervisor", 28.0))

    # TODO: change test when data isn't hardcoded and forecast() is implemented
    def test_forecast_accuracy(self):
        expected_forecast = 200 / 30
        actual_forecast = app_module.generate_forecast() / 30
        self.assertAlmostEqual(expected_forecast, actual_forecast)

if __name__ == "__main__":
    unittest.main()