"""Tests for the employee pages and the /api/employees routes (US-3).

Run all tests from the project folder with:
    python -m unittest discover -s tests -v
"""
import os
import sqlite3
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import app

PASSWORD = "pw12345"
PASSWORD_HASH = generate_password_hash(PASSWORD)
TOKEN = "test-csrf-token"

SCHEMA = """
CREATE TABLE SystemRoles(
    system_role_id INTEGER PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE,
    description TEXT);
CREATE TABLE Roles(
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT NOT NULL UNIQUE,
    system_role_id INTEGER NOT NULL);
CREATE TABLE Employees(
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    hourly_rate REAL NOT NULL,
    max_hours_per_week INTEGER NOT NULL DEFAULT 40,
    preferred_hours_per_week INTEGER NOT NULL DEFAULT 32,
    active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE Qualifications(
    qualification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    qualification_name TEXT NOT NULL UNIQUE);
CREATE TABLE EmployeeQualifications(
    employee_id INTEGER NOT NULL,
    qualification_id INTEGER NOT NULL,
    PRIMARY KEY (employee_id, qualification_id));
CREATE TABLE Users(
    userid INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    system_role_id INTEGER NOT NULL DEFAULT 0,
    employee_id INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1);

INSERT INTO SystemRoles VALUES
    (0, 'Unregistered', ''), (1, 'Associate', ''),
    (2, 'Manager', ''), (3, 'Administrator', '');
INSERT INTO Roles (role_name, system_role_id) VALUES
    ('Cashier', 1), ('Shift Lead', 2), ('Store Admin', 3);
INSERT INTO Employees (role_id, first_name, last_name, hourly_rate) VALUES
    (3, 'Alice', 'Admin', 40.0),
    (2, 'Mara', 'Manager', 30.0),
    (1, 'Abe', 'Associate', 15.0),
    (1, 'Bea', 'Associate', 16.0);
INSERT INTO Qualifications (qualification_name) VALUES
    ('Cash Handling'), ('Food Handler');
INSERT INTO EmployeeQualifications VALUES (3, 1);
"""

# Employees: 1 Alice (Administrator), 2 Mara (Manager), 3 Abe and 4 Bea (Associates)
# Logins:    admin -> Alice, manager -> Mara, assoc -> Abe


def new_employee(**changes):
    data = {"first_name": "Ana", "last_name": "Ruiz", "role_id": 1,
            "hourly_rate": 18.5, "max_hours_per_week": 40,
            "preferred_hours_per_week": 32}
    data.update(changes)
    return data


class RouteTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temp_directory.name, "routes.db")
        app.config.update(TESTING=True, DATABASE=self.database_path)

        connection = sqlite3.connect(self.database_path)
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO Users (username, password, system_role_id, employee_id) "
            "VALUES (?, ?, ?, ?)",
            [("admin", PASSWORD_HASH, 3, 1),
             ("manager", PASSWORD_HASH, 2, 2),
             ("assoc", PASSWORD_HASH, 1, 3)],
        )
        connection.commit()
        connection.close()

        self.client = app.test_client()
        self.headers = {"X-CSRF-Token": TOKEN}

    def tearDown(self):
        app.config["TESTING"] = False
        app.config["DATABASE"] = os.path.join("database", "workforce.db")
        self.temp_directory.cleanup()

    # ----- helpers --------------------------------------------------
    def sign_in(self, username):
        response = self.client.post(
            "/login", data={"username": username, "password": PASSWORD})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as flask_session:
            flask_session["csrf_token"] = TOKEN

    def query(self, sql, params=()):
        connection = sqlite3.connect(self.database_path)
        try:
            return connection.execute(sql, params).fetchall()
        finally:
            connection.close()

    def employee_row(self, employee_id):
        rows = self.query(
            "SELECT first_name, last_name, role_id, hourly_rate, "
            "max_hours_per_week, preferred_hours_per_week, active "
            "FROM Employees WHERE employee_id = ?", (employee_id,))
        return rows[0] if rows else None

    def form(self, **changes):
        data = {"first_name": "Ana", "last_name": "Ruiz", "role_id": "1",
                "hourly_rate": "18.50", "max_hours_per_week": "40",
                "preferred_hours_per_week": "32", "csrf_token": TOKEN}
        data.update(changes)
        return data


# ======================================================================
# Access rules, CSRF and the error format
# ======================================================================
class AccessTests(RouteTestCase):
    def test_api_requires_sign_in(self):
        response = self.client.get("/api/employees")
        self.assertEqual(response.status_code, 401)
        error = response.get_json()["error"]
        self.assertEqual(error["code"], "UNAUTHENTICATED")
        self.assertIn("request_id", error)

    def test_api_write_without_sign_in_is_401_not_csrf(self):
        response = self.client.post("/api/employees", json=new_employee())
        self.assertEqual(response.status_code, 401)

    def test_pages_require_sign_in(self):
        for path in ("/employees", "/employees/1", "/employees/new",
                     "/employees/1/edit"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, msg=path)
            self.assertIn("/login", response.location, msg=path)

    def test_associate_cannot_use_manager_api(self):
        self.sign_in("assoc")
        self.assertEqual(self.client.get("/api/employees").status_code, 403)
        for response in (
            self.client.post("/api/employees", json=new_employee(),
                             headers=self.headers),
            self.client.put("/api/employees/4", json=new_employee(),
                            headers=self.headers),
            self.client.delete("/api/employees/4", headers=self.headers),
            self.client.put("/api/employees/4/qualifications",
                            json={"qualification_ids": [1]},
                            headers=self.headers),
        ):
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.get_json()["error"]["code"], "FORBIDDEN")
        self.assertEqual(self.employee_row(4)[6], 1)  # still active

    def test_missing_or_wrong_csrf_token_is_rejected(self):
        self.sign_in("manager")
        for headers in ({}, {"X-CSRF-Token": "wrong"}):
            response = self.client.post("/api/employees", json=new_employee(),
                                        headers=headers)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.get_json()["error"]["code"],
                             "CSRF_FAILED")
        self.assertEqual(len(self.query("SELECT 1 FROM Employees")), 4)

    def test_form_post_without_csrf_token_is_rejected(self):
        self.sign_in("manager")
        data = self.form()
        del data["csrf_token"]
        response = self.client.post("/employees/new", data=data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(self.query("SELECT 1 FROM Employees")), 4)

    def test_forms_contain_the_session_csrf_token(self):
        self.sign_in("manager")
        response = self.client.get("/employees/new")
        with self.client.session_transaction() as flask_session:
            token = flask_session["csrf_token"]
        self.assertIn(f'name="csrf_token" value="{token}"'.encode(),
                      response.data)


# ======================================================================
# JSON API
# ======================================================================
class ApiReadTests(RouteTestCase):
    def test_manager_list_has_paging_fields(self):
        self.sign_in("manager")
        body = self.client.get("/api/employees").get_json()
        self.assertEqual(body["total"], 4)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 25)
        self.assertEqual(len(body["items"]), 4)
        # sorted by last name: Admin, Associate, Associate, Manager
        self.assertEqual([i["first_name"] for i in body["items"]],
                         ["Alice", "Abe", "Bea", "Mara"])

    def test_manager_sees_associate_and_own_wages_only(self):
        self.sign_in("manager")
        items = {i["first_name"]: i for i in
                 self.client.get("/api/employees").get_json()["items"]}
        self.assertEqual(items["Abe"]["hourly_rate"], 15.0)
        self.assertEqual(items["Bea"]["hourly_rate"], 16.0)
        self.assertEqual(items["Mara"]["hourly_rate"], 30.0)
        self.assertNotIn("hourly_rate", items["Alice"])

    def test_administrator_sees_every_wage(self):
        self.sign_in("admin")
        items = self.client.get("/api/employees").get_json()["items"]
        self.assertTrue(all("hourly_rate" in i for i in items))

    def test_search_by_name_role_and_qualification(self):
        self.sign_in("manager")

        def names(text):
            body = self.client.get("/api/employees",
                                   query_string={"search": text}).get_json()
            return [i["first_name"] for i in body["items"]]

        self.assertEqual(names("bea"), ["Bea"])
        self.assertEqual(names("Shift Lead"), ["Mara"])
        self.assertEqual(names("handling"), ["Abe"])  # Abe has Cash Handling
        self.assertEqual(names("cash"), ["Abe", "Bea"])  # qualification or role
        self.assertEqual(names("nobody"), [])

    def test_paging(self):
        self.sign_in("manager")
        first = self.client.get("/api/employees?page=1&page_size=3").get_json()
        second = self.client.get("/api/employees?page=2&page_size=3").get_json()
        self.assertEqual(len(first["items"]), 3)
        self.assertEqual(len(second["items"]), 1)
        self.assertEqual(second["total"], 4)

    def test_bad_paging_values_are_rejected(self):
        self.sign_in("manager")
        for query in ("page=0", "page=x", "page_size=0", "page_size=101"):
            response = self.client.get("/api/employees?" + query)
            self.assertEqual(response.status_code, 400, msg=query)
            self.assertEqual(response.get_json()["error"]["code"],
                             "VALIDATION_ERROR")

    def test_get_one_employee(self):
        self.sign_in("manager")
        body = self.client.get("/api/employees/3").get_json()
        self.assertEqual(body["first_name"], "Abe")
        self.assertEqual(body["qualification_ids"], [1])
        self.assertEqual(body["active"], True)

    def test_get_unknown_employee_is_404(self):
        self.sign_in("manager")
        response = self.client.get("/api/employees/999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"]["code"], "NOT_FOUND")

    def test_associate_can_read_only_their_own_record(self):
        self.sign_in("assoc")
        own = self.client.get("/api/employees/3")
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.get_json()["first_name"], "Abe")
        self.assertEqual(self.client.get("/api/employees/4").status_code, 403)


class ApiWriteTests(RouteTestCase):
    def test_create_employee(self):
        self.sign_in("manager")
        response = self.client.post(
            "/api/employees",
            json=new_employee(qualification_ids=[1, 2]),
            headers=self.headers)
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["first_name"], "Ana")
        self.assertEqual(body["hourly_rate"], 18.5)
        self.assertEqual(body["qualification_ids"], [1, 2])
        # it was really saved
        saved = self.employee_row(body["employee_id"])
        self.assertEqual(saved[:2], ("Ana", "Ruiz"))
        self.assertEqual(
            self.query("SELECT COUNT(*) FROM EmployeeQualifications "
                       "WHERE employee_id = ?", (body["employee_id"],))[0][0],
            2)

    def test_create_with_bad_data_reports_every_problem_and_saves_nothing(self):
        self.sign_in("manager")
        response = self.client.post(
            "/api/employees",
            json=new_employee(first_name="", last_name="x" * 51, role_id=99,
                              hourly_rate=0, max_hours_per_week=81,
                              preferred_hours_per_week=-1),
            headers=self.headers)
        self.assertEqual(response.status_code, 400)
        error = response.get_json()["error"]
        self.assertEqual(error["code"], "VALIDATION_ERROR")
        fields = {d["field"] for d in error["details"]}
        self.assertEqual(fields, {"first_name", "last_name", "role_id",
                                  "hourly_rate", "max_hours_per_week",
                                  "preferred_hours_per_week"})
        self.assertEqual(len(self.query("SELECT 1 FROM Employees")), 4)

    def test_preferred_hours_cannot_exceed_max(self):
        self.sign_in("manager")
        response = self.client.post(
            "/api/employees",
            json=new_employee(max_hours_per_week=20,
                              preferred_hours_per_week=30),
            headers=self.headers)
        self.assertEqual(response.status_code, 400)
        details = response.get_json()["error"]["details"]
        self.assertEqual(details[0]["field"], "preferred_hours_per_week")

    def test_body_must_be_a_json_object(self):
        self.sign_in("manager")
        for body in ("not json", "[1, 2]"):
            response = self.client.post(
                "/api/employees", data=body,
                headers={**self.headers, "Content-Type": "application/json"})
            self.assertEqual(response.status_code, 400, msg=body)
            self.assertEqual(response.get_json()["error"]["code"],
                             "VALIDATION_ERROR")

    def test_update_employee(self):
        self.sign_in("manager")
        response = self.client.put(
            "/api/employees/4",
            json=new_employee(first_name="Beatrice", last_name="Associate",
                              role_id=1, hourly_rate=17.25,
                              max_hours_per_week=30,
                              preferred_hours_per_week=20),
            headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["first_name"], "Beatrice")
        self.assertEqual(self.employee_row(4),
                         ("Beatrice", "Associate", 1, 17.25, 30, 20, 1))

    def test_update_keeps_hours_that_were_left_out(self):
        self.sign_in("manager")
        self.client.put("/api/employees/4",
                        json=new_employee(max_hours_per_week=20,
                                          preferred_hours_per_week=10),
                        headers=self.headers)
        body = new_employee(first_name="Beatrice")
        del body["max_hours_per_week"]
        del body["preferred_hours_per_week"]
        response = self.client.put("/api/employees/4", json=body,
                                   headers=self.headers)
        self.assertEqual(response.status_code, 200)
        saved = self.employee_row(4)
        self.assertEqual(saved[4:6], (20, 10))

    def test_update_keeps_qualifications_unless_they_are_sent(self):
        self.sign_in("manager")
        response = self.client.put(
            "/api/employees/3", json=new_employee(first_name="Abel"),
            headers=self.headers)
        self.assertEqual(response.get_json()["qualification_ids"], [1])

    def test_manager_cannot_change_a_wage_they_cannot_see(self):
        self.sign_in("manager")
        response = self.client.put(
            "/api/employees/1",
            json=new_employee(first_name="Alice", last_name="Admin",
                              role_id=3, hourly_rate=99),
            headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("hourly_rate", response.get_json())
        self.assertEqual(self.employee_row(1)[3], 40.0)

    def test_update_with_bad_data_changes_nothing(self):
        self.sign_in("manager")
        before = self.employee_row(4)
        response = self.client.put(
            "/api/employees/4", json=new_employee(hourly_rate=501),
            headers=self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.employee_row(4), before)

    def test_update_unknown_employee_is_404(self):
        self.sign_in("manager")
        response = self.client.put("/api/employees/999", json=new_employee(),
                                   headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_delete_deactivates_instead_of_deleting(self):
        self.sign_in("manager")
        response = self.client.delete("/api/employees/4", headers=self.headers)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.employee_row(4)[6], 0)  # row is still there

        default = self.client.get("/api/employees").get_json()
        self.assertEqual(default["total"], 3)
        everyone = self.client.get(
            "/api/employees?include_inactive=true").get_json()
        self.assertEqual(everyone["total"], 4)
        bea = [i for i in everyone["items"] if i["first_name"] == "Bea"][0]
        self.assertEqual(bea["active"], False)

    def test_delete_unknown_employee_is_404(self):
        self.sign_in("manager")
        response = self.client.delete("/api/employees/999",
                                      headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_set_qualifications(self):
        self.sign_in("manager")
        response = self.client.put("/api/employees/4/qualifications",
                                   json={"qualification_ids": [2, 1]},
                                   headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["qualification_ids"], [1, 2])
        cleared = self.client.put("/api/employees/4/qualifications",
                                  json={"qualification_ids": []},
                                  headers=self.headers)
        self.assertEqual(cleared.get_json()["qualification_ids"], [])

    def test_set_qualifications_rejects_bad_input(self):
        self.sign_in("manager")
        for body in ({}, {"qualification_ids": [99]},
                     {"qualification_ids": "1"}, {"qualification_ids": ["a"]}):
            response = self.client.put("/api/employees/3/qualifications",
                                       json=body, headers=self.headers)
            self.assertEqual(response.status_code, 400, msg=str(body))
        # Abe's original qualification is untouched
        self.assertEqual(
            self.query("SELECT qualification_id FROM EmployeeQualifications "
                       "WHERE employee_id = 3"), [(1,)])

    def test_set_qualifications_for_unknown_employee_is_404(self):
        self.sign_in("manager")
        response = self.client.put("/api/employees/999/qualifications",
                                   json={"qualification_ids": [1]},
                                   headers=self.headers)
        self.assertEqual(response.status_code, 404)


# ======================================================================
# Pages
# ======================================================================
class PageTests(RouteTestCase):
    def test_associate_directory_hides_other_wages_and_add_button(self):
        self.sign_in("assoc")
        response = self.client.get("/employees")
        self.assertEqual(response.status_code, 200)
        page = response.data.decode()
        self.assertIn("Employee Directory", page)
        self.assertIn("Bea", page)
        self.assertIn("$15.00", page)          # their own wage
        for hidden in ("$16.00", "$30.00", "$40.00"):
            self.assertNotIn(hidden, page)
        self.assertNotIn("Add Employee", page)
        self.assertNotIn("/edit", page)

    def test_manager_page_shows_allowed_wages_and_add_button(self):
        self.sign_in("manager")
        page = self.client.get("/employees").data.decode()
        self.assertIn("Employee Management", page)
        self.assertIn("Add Employee", page)
        for shown in ("$15.00", "$16.00", "$30.00"):
            self.assertIn(shown, page)
        self.assertNotIn("$40.00", page)       # the Administrator's wage

    def test_page_search(self):
        self.sign_in("manager")
        page = self.client.get("/employees?search=Bea").data.decode()
        self.assertIn("Bea", page)
        self.assertNotIn("Abe", page)
        empty = self.client.get("/employees?search=zzz").data.decode()
        self.assertIn("No employees match", empty)

    def test_inactive_employees_are_hidden_until_requested(self):
        self.sign_in("manager")
        self.client.post("/employees/4/deactivate",
                         data={"csrf_token": TOKEN})
        self.client.get("/employees")  # shows (and clears) the "deactivated" message
        self.assertNotIn("Bea", self.client.get("/employees").data.decode())
        shown = self.client.get("/employees?show_inactive=1").data.decode()
        self.assertIn("Bea", shown)
        self.assertIn("Inactive", shown)

    def test_add_employee_page_creates_the_employee(self):
        self.sign_in("manager")
        response = self.client.post(
            "/employees/new",
            data={**self.form(), "qualification_ids": ["1", "2"]})
        self.assertEqual(response.status_code, 302)
        self.assertRegex(response.location, r"/employees/\d+$")
        saved = self.query("SELECT employee_id, first_name, hourly_rate "
                           "FROM Employees WHERE first_name = 'Ana'")
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0][2], 18.5)
        quals = self.query("SELECT qualification_id FROM EmployeeQualifications "
                           "WHERE employee_id = ? ORDER BY 1", (saved[0][0],))
        self.assertEqual(quals, [(1,), (2,)])

        detail = self.client.get(response.location).data.decode()
        self.assertIn("Ana Ruiz", detail)
        self.assertIn("Cash Handling, Food Handler", detail)
        self.assertIn("Ana Ruiz was added.", detail)

    def test_add_form_shows_errors_and_keeps_what_was_typed(self):
        self.sign_in("manager")
        response = self.client.post(
            "/employees/new",
            data=self.form(first_name="", last_name="Keepme", hourly_rate="0"))
        self.assertEqual(response.status_code, 400)
        page = response.data.decode()
        self.assertIn("First name is required.", page)
        self.assertIn("Hourly rate must be greater than 0", page)
        self.assertIn('value="Keepme"', page)
        self.assertEqual(len(self.query("SELECT 1 FROM Employees")), 4)

    def test_names_are_escaped_on_the_page(self):
        self.sign_in("manager")
        response = self.client.post(
            "/employees/new", data=self.form(first_name="<b>Zed</b>"))
        self.assertEqual(response.status_code, 302)
        page = self.client.get("/employees").data.decode()
        self.assertIn("&lt;b&gt;Zed&lt;/b&gt;", page)
        self.assertNotIn("<b>Zed</b>", page)

    def test_associate_cannot_open_manager_pages(self):
        self.sign_in("assoc")
        self.assertEqual(self.client.get("/employees/new").status_code, 403)
        self.assertEqual(self.client.get("/employees/4/edit").status_code, 403)
        self.assertEqual(
            self.client.post("/employees/new", data=self.form()).status_code,
            403)
        self.assertEqual(
            self.client.post("/employees/4/deactivate",
                             data={"csrf_token": TOKEN}).status_code, 403)
        self.assertEqual(len(self.query("SELECT 1 FROM Employees")), 4)

    def test_detail_page_rules(self):
        self.sign_in("assoc")
        self.assertEqual(self.client.get("/employees/3").status_code, 200)
        self.assertEqual(self.client.get("/employees/4").status_code, 403)
        self.client.get("/logout")
        self.sign_in("manager")
        self.assertEqual(self.client.get("/employees/4").status_code, 200)
        self.assertEqual(self.client.get("/employees/999").status_code, 404)

    def test_detail_hides_a_wage_the_viewer_may_not_see(self):
        self.sign_in("manager")
        page = self.client.get("/employees/1").data.decode()
        self.assertIn("Alice Admin", page)
        self.assertIn("Hidden for your account", page)
        self.assertNotIn("$40.00", page)

    def test_edit_form_is_prefilled(self):
        self.sign_in("manager")
        page = self.client.get("/employees/3/edit").data.decode()
        self.assertIn('value="Abe"', page)
        self.assertIn('value="15.0"', page)
        self.assertRegex(page, r'value="1"\s+checked')  # Cash Handling ticked

    def test_edit_page_saves_changes(self):
        self.sign_in("manager")
        response = self.client.post(
            "/employees/4/edit",
            data=self.form(first_name="Beatrice", last_name="Associate",
                           hourly_rate="17.00", max_hours_per_week="30",
                           preferred_hours_per_week="20"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.employee_row(4),
                         ("Beatrice", "Associate", 1, 17.0, 30, 20, 1))
        # no qualification boxes ticked, so they were all cleared
        self.assertEqual(
            self.query("SELECT 1 FROM EmployeeQualifications "
                       "WHERE employee_id = 4"), [])

    def test_edit_page_can_untick_qualifications(self):
        self.sign_in("manager")
        self.client.post("/employees/3/edit", data=self.form())
        self.assertEqual(
            self.query("SELECT 1 FROM EmployeeQualifications "
                       "WHERE employee_id = 3"), [])

    def test_edit_page_with_bad_data_changes_nothing(self):
        self.sign_in("manager")
        before = self.employee_row(4)
        response = self.client.post(
            "/employees/4/edit", data=self.form(max_hours_per_week="200"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("Must be a whole number from 1 to 80.",
                      response.data.decode())
        self.assertEqual(self.employee_row(4), before)

    def test_edit_page_keeps_a_wage_the_editor_cannot_see(self):
        self.sign_in("manager")
        page = self.client.get("/employees/1/edit").data.decode()
        self.assertIn("Hidden for your account", page)
        self.assertNotIn('name="hourly_rate"', page)
        response = self.client.post(
            "/employees/1/edit",
            data=self.form(first_name="Alicia", last_name="Admin",
                           role_id="3", hourly_rate="99"))
        self.assertEqual(response.status_code, 302)
        saved = self.employee_row(1)
        self.assertEqual(saved[0], "Alicia")
        self.assertEqual(saved[3], 40.0)

    def test_deactivate_page(self):
        self.sign_in("manager")
        response = self.client.post("/employees/4/deactivate",
                                    data={"csrf_token": TOKEN})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.employee_row(4)[6], 0)
        listing = self.client.get("/employees").data.decode()
        self.assertIn("Bea Associate was deactivated.", listing)

    def test_edit_or_deactivate_unknown_employee_is_404(self):
        self.sign_in("manager")
        self.assertEqual(self.client.get("/employees/999/edit").status_code,
                         404)
        self.assertEqual(
            self.client.post("/employees/999/deactivate",
                             data={"csrf_token": TOKEN}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
