"""Data layer for the Employee Management module (SDS section 4).

This is the ONLY place that contains SQL for Employees, Qualifications and
EmployeeQualifications. Every query is parameterized. Methods return plain
dictionaries; the service layer turns them into Employee objects.

The repository never commits. The service decides when a transaction ends.
"""


def _rows(cursor):
    """Convert the cursor's rows into a list of dictionaries."""
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


class EmployeeRepository:
    def __init__(self, conn):
        self.conn = conn

    # ----- transaction control ------------------------------------
    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    # ----- employees ----------------------------------------------
    def list_employees(self, search=None, include_inactive=False):
        sql = """
            SELECT e.employee_id, e.first_name, e.last_name, e.role_id,
                   e.hourly_rate, e.max_hours_per_week,
                   e.preferred_hours_per_week, e.active
            FROM Employees e
            JOIN Roles r ON r.role_id = e.role_id
        """
        conditions, params = [], []
        if not include_inactive:
            conditions.append("e.active = 1")
        if search:
            like = f"%{search}%"
            conditions.append("""(
                e.first_name LIKE ?
                OR e.last_name LIKE ?
                OR (e.first_name || ' ' || e.last_name) LIKE ?
                OR r.role_name LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM EmployeeQualifications eq
                    JOIN Qualifications q
                      ON q.qualification_id = eq.qualification_id
                    WHERE eq.employee_id = e.employee_id
                      AND q.qualification_name LIKE ?
                )
            )""")
            params.extend([like] * 5)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY e.last_name, e.first_name, e.employee_id"
        cursor = self.conn.execute(sql, params)
        return _rows(cursor)

    def get_employee(self, employee_id):
        cursor = self.conn.execute(
            """
            SELECT employee_id, first_name, last_name, role_id, hourly_rate,
                   max_hours_per_week, preferred_hours_per_week, active
            FROM Employees WHERE employee_id = ?
            """,
            (employee_id,),
        )
        rows = _rows(cursor)
        return rows[0] if rows else None

    def insert_employee(self, data):
        cursor = self.conn.execute(
            """
            INSERT INTO Employees
                (role_id, first_name, last_name, hourly_rate,
                 max_hours_per_week, preferred_hours_per_week, active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (data["role_id"], data["first_name"], data["last_name"],
             data["hourly_rate"], data["max_hours_per_week"],
             data["preferred_hours_per_week"]),
        )
        return cursor.lastrowid

    def update_employee(self, employee_id, data):
        cursor = self.conn.execute(
            """
            UPDATE Employees
            SET role_id = ?, first_name = ?, last_name = ?, hourly_rate = ?,
                max_hours_per_week = ?, preferred_hours_per_week = ?
            WHERE employee_id = ?
            """,
            (data["role_id"], data["first_name"], data["last_name"],
             data["hourly_rate"], data["max_hours_per_week"],
             data["preferred_hours_per_week"], employee_id),
        )
        return cursor.rowcount > 0

    def set_active(self, employee_id, active):
        cursor = self.conn.execute(
            "UPDATE Employees SET active = ? WHERE employee_id = ?",
            (1 if active else 0, employee_id),
        )
        return cursor.rowcount > 0

    # ----- roles --------------------------------------------------
    def role_exists(self, role_id):
        cursor = self.conn.execute(
            "SELECT 1 FROM Roles WHERE role_id = ?", (role_id,)
        )
        return cursor.fetchone() is not None

    def list_roles(self):
        cursor = self.conn.execute(
            "SELECT role_id, role_name FROM Roles ORDER BY role_name"
        )
        return _rows(cursor)

    def get_system_role_id(self, role_id):
        cursor = self.conn.execute(
            "SELECT system_role_id FROM Roles WHERE role_id = ?", (role_id,)
        )
        row = cursor.fetchone()
        return row["system_role_id"] if row is not None else None

    # ----- qualifications -----------------------------------------
    def list_qualifications(self):
        cursor = self.conn.execute(
            "SELECT qualification_id, qualification_name "
            "FROM Qualifications ORDER BY qualification_name"
        )
        return _rows(cursor)

    def existing_qualification_ids(self, ids):
        """Return the subset of ids that exist in Qualifications."""
        ids = list(ids)
        if not ids:
            return set()
        marks = ",".join("?" for _ in ids)
        cursor = self.conn.execute(
            f"SELECT qualification_id FROM Qualifications "
            f"WHERE qualification_id IN ({marks})",
            ids,
        )
        return {row[0] for row in cursor.fetchall()}

    def get_qualification_ids(self, employee_id):
        cursor = self.conn.execute(
            "SELECT qualification_id FROM EmployeeQualifications "
            "WHERE employee_id = ? ORDER BY qualification_id",
            (employee_id,),
        )
        return [row[0] for row in cursor.fetchall()]

    def get_all_qualification_ids(self):
        """Return {employee_id: [qualification_id, ...]} in one query."""
        cursor = self.conn.execute(
            "SELECT employee_id, qualification_id FROM EmployeeQualifications "
            "ORDER BY employee_id, qualification_id"
        )
        result = {}
        for employee_id, qualification_id in cursor.fetchall():
            result.setdefault(employee_id, []).append(qualification_id)
        return result

    def replace_qualifications(self, employee_id, qualification_ids):
        self.conn.execute(
            "DELETE FROM EmployeeQualifications WHERE employee_id = ?",
            (employee_id,),
        )
        for qualification_id in sorted(set(qualification_ids)):
            self.conn.execute(
                "INSERT INTO EmployeeQualifications "
                "(employee_id, qualification_id) VALUES (?, ?)",
                (employee_id, qualification_id),
            )
