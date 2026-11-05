import sqlite3
import unittest

import employee_service as svc


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE Roles(role_id INTEGER PRIMARY KEY AUTOINCREMENT,
                           role_name TEXT NOT NULL UNIQUE);
        CREATE TABLE Employees(employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                               role_id INTEGER NOT NULL,
                               first_name TEXT NOT NULL,
                               last_name TEXT NOT NULL,
                               hourly_wage REAL NOT NULL);
        CREATE TABLE Qualifications(qualification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    qualification_name TEXT NOT NULL UNIQUE);
        CREATE TABLE EmployeeQualifications(employee_id INTEGER NOT NULL,
                                            qualification_id INTEGER NOT NULL,
                                            PRIMARY KEY (employee_id, qualification_id));
        CREATE TABLE Users(userid INTEGER PRIMARY KEY AUTOINCREMENT,
                           username TEXT, employee_id INTEGER NOT NULL);
        INSERT INTO Roles (role_name) VALUES ('Cashier'), ('Cook');
        INSERT INTO Qualifications (qualification_name)
            VALUES ('Cash Handling'), ('Food Handler');
    """)
    return conn


class EmployeeServiceTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_db()

    def tearDown(self):
        self.conn.close()

    def _create(self, first="Ana", last="Lopez", role=1, wage="15.50", quals=(1,)):
        clean, errors = svc.validate_employee(self.conn, first, last, role, wage)
        self.assertEqual(errors, [])
        return svc.create_employee(self.conn, clean, list(quals))

    def test_validate_accepts_good_data(self):
        clean, errors = svc.validate_employee(self.conn, " Ana ", "Lopez", "1", "15.5")
        self.assertEqual(errors, [])
        self.assertEqual(clean["first_name"], "Ana")
        self.assertEqual(clean["hourly_wage"], 15.5)

    def test_validate_rejects_bad_data(self):
        _, errors = svc.validate_employee(self.conn, "", "", 99, "abc")
        self.assertEqual(len(errors), 4)

    def test_validate_rejects_negative_wage(self):
        _, errors = svc.validate_employee(self.conn, "A", "B", 1, "-5")
        self.assertTrue(any("wage" in e.lower() for e in errors))

    def test_create_and_get(self):
        emp_id = self._create(quals=(1, 2))
        employee, qual_ids = svc.get_employee(self.conn, emp_id)
        self.assertEqual(employee["first_name"], "Ana")
        self.assertEqual(employee["role_name"], "Cashier")
        self.assertEqual(sorted(qual_ids), [1, 2])

    def test_get_missing_employee(self):
        employee, qual_ids = svc.get_employee(self.conn, 999)
        self.assertIsNone(employee)
        self.assertEqual(qual_ids, [])

    def test_update(self):
        emp_id = self._create()
        clean, _ = svc.validate_employee(self.conn, "Ana", "Garcia", 2, "18")
        self.assertTrue(svc.update_employee(self.conn, emp_id, clean, [2]))
        employee, qual_ids = svc.get_employee(self.conn, emp_id)
        self.assertEqual(employee["last_name"], "Garcia")
        self.assertEqual(employee["role_name"], "Cook")
        self.assertEqual(qual_ids, [2])

    def test_update_missing_returns_false(self):
        clean, _ = svc.validate_employee(self.conn, "A", "B", 1, "10")
        self.assertFalse(svc.update_employee(self.conn, 999, clean, []))

    def test_delete(self):
        emp_id = self._create()
        self.assertTrue(svc.delete_employee(self.conn, emp_id))
        self.assertIsNone(svc.get_employee(self.conn, emp_id)[0])

    def test_delete_blocked_when_user_linked(self):
        emp_id = self._create()
        self.conn.execute("INSERT INTO Users (username, employee_id) VALUES ('ana', ?)",
                          (emp_id,))
        with self.assertRaises(ValueError):
            svc.delete_employee(self.conn, emp_id)

    def test_search(self):
        self._create(first="Ana", last="Lopez", role=1, quals=(1,))
        self._create(first="Ben", last="Cook", role=2, quals=(2,))
        self.assertEqual(len(svc.list_employees(self.conn)), 2)
        self.assertEqual(len(svc.list_employees(self.conn, "ana")), 1)
        self.assertEqual(len(svc.list_employees(self.conn, "Cook")), 1)
        self.assertEqual(len(svc.list_employees(self.conn, "Food Handler")), 1)
        self.assertEqual(len(svc.list_employees(self.conn, "zzz")), 0)

    def test_create_qualification_rejects_duplicates_and_blanks(self):
        self.assertIsNotNone(svc.create_qualification(self.conn, "First Aid"))
        self.assertIsNone(svc.create_qualification(self.conn, "first aid"))
        self.assertIsNone(svc.create_qualification(self.conn, "   "))


if __name__ == "__main__":
    unittest.main()