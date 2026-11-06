import sqlite3
import unittest

from errors import NotFoundError, ValidationError
from repositories.employee_repository import EmployeeRepository
from services.employee_service import EmployeeService

SCHEMA = """
CREATE TABLE Roles(
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT NOT NULL UNIQUE);
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
INSERT INTO Roles (role_name) VALUES ('Cashier'), ('Cook');
INSERT INTO Qualifications (qualification_name)
    VALUES ('Cash Handling'), ('Food Handler');
"""


def valid(**changes):
    data = {"first_name": "Ana", "last_name": "Ruiz", "role_id": 1,
            "hourly_rate": 18.5, "max_hours_per_week": 40,
            "preferred_hours_per_week": 32}
    data.update(changes)
    return data


class EmployeeServiceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(SCHEMA)
        self.service = EmployeeService(EmployeeRepository(self.conn))

    def tearDown(self):
        self.conn.close()

    def fields_with_errors(self, data):
        with self.assertRaises(ValidationError) as context:
            self.service.create_employee(data)
        return {d["field"] for d in context.exception.details}

    # ----- create / read ------------------------------------------
    def test_create_and_get(self):
        created = self.service.create_employee(valid(qualification_ids=[1, 2]))
        fetched = self.service.get_employee(created.employee_id)
        self.assertEqual(fetched.first_name, "Ana")
        self.assertEqual(fetched.hourly_rate, 18.5)
        self.assertTrue(fetched.active)
        self.assertEqual(fetched.qualification_ids, (1, 2))

    def test_create_uses_hour_defaults(self):
        data = valid()
        del data["max_hours_per_week"]
        del data["preferred_hours_per_week"]
        employee = self.service.create_employee(data)
        self.assertEqual(employee.max_hours_per_week, 40)
        self.assertEqual(employee.preferred_hours_per_week, 32)

    def test_names_are_trimmed(self):
        employee = self.service.create_employee(valid(first_name="  Ana  "))
        self.assertEqual(employee.first_name, "Ana")

    def test_get_missing_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            self.service.get_employee(999)

    # ----- validation (SDS section 8.7) ---------------------------
    def test_names_required_and_max_50(self):
        self.assertEqual(self.fields_with_errors(valid(first_name="  ")),
                         {"first_name"})
        self.assertEqual(self.fields_with_errors(valid(last_name="x" * 51)),
                         {"last_name"})
        self.service.create_employee(valid(last_name="x" * 50))

    def test_hourly_rate_rules(self):
        for bad in (0, -1, 500.01, "abc", None, float("nan")):
            self.assertEqual(self.fields_with_errors(valid(hourly_rate=bad)),
                             {"hourly_rate"}, msg=f"rate {bad!r}")
        self.service.create_employee(valid(hourly_rate=500))

    def test_max_hours_rules(self):
        for bad in (0, 81, "x", 40.5):
            self.assertEqual(
                self.fields_with_errors(valid(max_hours_per_week=bad)),
                {"max_hours_per_week"}, msg=f"max {bad!r}")
        self.service.create_employee(valid(max_hours_per_week=80,
                                           preferred_hours_per_week=80))

    def test_preferred_cannot_exceed_max(self):
        fields = self.fields_with_errors(
            valid(max_hours_per_week=20, preferred_hours_per_week=30))
        self.assertEqual(fields, {"preferred_hours_per_week"})

    def test_unknown_role_rejected(self):
        self.assertEqual(self.fields_with_errors(valid(role_id=99)),
                         {"role_id"})
        self.assertEqual(self.fields_with_errors(valid(role_id=None)),
                         {"role_id"})

    def test_all_problems_reported_together(self):
        fields = self.fields_with_errors(
            {"first_name": "", "last_name": "", "role_id": 99,
             "hourly_rate": -5})
        self.assertEqual(fields, {"first_name", "last_name", "role_id",
                                  "hourly_rate"})

    def test_failed_create_saves_nothing(self):
        self.fields_with_errors(valid(hourly_rate=-1))
        self.assertEqual(self.service.list_employees(include_inactive=True), [])

    def test_unknown_qualification_rejected_and_nothing_saved(self):
        self.assertEqual(
            self.fields_with_errors(valid(qualification_ids=[1, 42])),
            {"qualification_ids"})
        self.assertEqual(self.service.list_employees(include_inactive=True), [])

    # ----- update -------------------------------------------------
    def test_update_changes_fields_and_keeps_qualifications(self):
        created = self.service.create_employee(valid(qualification_ids=[1]))
        updated = self.service.update_employee(
            created.employee_id,
            valid(last_name="Garcia", role_id=2, hourly_rate=20))
        self.assertEqual(updated.last_name, "Garcia")
        self.assertEqual(updated.role_id, 2)
        self.assertEqual(updated.qualification_ids, (1,))

    def test_update_can_replace_qualifications(self):
        created = self.service.create_employee(valid(qualification_ids=[1]))
        updated = self.service.update_employee(
            created.employee_id, valid(qualification_ids=[2]))
        self.assertEqual(updated.qualification_ids, (2,))

    def test_update_missing_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            self.service.update_employee(999, valid())

    def test_update_invalid_changes_nothing(self):
        created = self.service.create_employee(valid())
        with self.assertRaises(ValidationError):
            self.service.update_employee(created.employee_id,
                                         valid(hourly_rate=0))
        self.assertEqual(
            self.service.get_employee(created.employee_id).hourly_rate, 18.5)

    # ----- deactivate / list / search -----------------------------
    def test_deactivate_hides_from_default_list(self):
        created = self.service.create_employee(valid())
        self.service.deactivate_employee(created.employee_id)
        self.assertEqual(self.service.list_employees(), [])
        self.assertEqual(len(self.service.list_employees(include_inactive=True)), 1)
        self.assertFalse(self.service.get_employee(created.employee_id).active)

    def test_deactivate_missing_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            self.service.deactivate_employee(999)

    def test_set_qualifications(self):
        created = self.service.create_employee(valid())
        updated = self.service.set_qualifications(created.employee_id, [2, 1, 2])
        self.assertEqual(updated.qualification_ids, (1, 2))
        cleared = self.service.set_qualifications(created.employee_id, [])
        self.assertEqual(cleared.qualification_ids, ())
        with self.assertRaises(NotFoundError):
            self.service.set_qualifications(999, [1])
        with self.assertRaises(ValidationError):
            self.service.set_qualifications(created.employee_id, [77])

    def test_search(self):
        self.service.create_employee(
            valid(first_name="Ana", last_name="Lopez", role_id=1,
                  qualification_ids=[1]))
        self.service.create_employee(
            valid(first_name="Ben", last_name="Smith", role_id=2,
                  qualification_ids=[2]))
        count = lambda text: len(self.service.list_employees(search=text))
        self.assertEqual(count(None), 2)
        self.assertEqual(count("  "), 2)
        self.assertEqual(count("ana"), 1)
        self.assertEqual(count("Ana Lopez"), 1)
        self.assertEqual(count("Cook"), 1)
        self.assertEqual(count("Food Handler"), 1)
        self.assertEqual(count("zzz"), 0)

    def test_search_is_not_sql_injectable(self):
        self.service.create_employee(valid())
        self.assertEqual(
            len(self.service.list_employees(search="' OR '1'='1")), 0)

    def test_list_is_sorted_by_last_then_first_name(self):
        self.service.create_employee(valid(first_name="Zed", last_name="Adams"))
        self.service.create_employee(valid(first_name="Amy", last_name="Adams"))
        self.service.create_employee(valid(first_name="Bob", last_name="Baker"))
        names = [(e.last_name, e.first_name)
                 for e in self.service.list_employees()]
        self.assertEqual(names, [("Adams", "Amy"), ("Adams", "Zed"),
                                 ("Baker", "Bob")])

    # ----- output hiding ------------------------------------------
    def test_rate_can_be_hidden_for_employee_role(self):
        employee = self.service.create_employee(valid())
        self.assertIn("hourly_rate", employee.to_dict())
        self.assertNotIn("hourly_rate", employee.to_dict(include_rate=False))


if __name__ == "__main__":
    unittest.main()
