"""AssistantData: read-only data access for the assistant (SDS 4.2, 8.6).

The assistant never writes and never runs its own SQL. It reads employees,
roles and qualifications through EmployeeService and availability through the
availability module. The four loaders are injectable so tests use fakes.
"""


class AssistantData:
    def __init__(self, load_employees, load_roles, load_qualifications,
                 load_availability):
        self._employees = load_employees
        self._roles = load_roles
        self._qualifications = load_qualifications
        self._availability = load_availability

    def employees(self):
        return [e for e in self._employees() if e.active]

    def role_names(self):
        return {r["role_id"]: r["role_name"] for r in self._roles()}

    def qualification_names(self):
        return {q["qualification_id"]: q["qualification_name"]
                for q in self._qualifications()}

    def shift_names(self):
        """{shift_id: shift_name} for shifts that have availability rows."""
        return {row["shift_id"]: row["shift_name"]
                for row in self._availability()}

    def available_employee_ids(self, shift_id):
        return {row["employee_id"] for row in self._availability()
                if row["shift_id"] == shift_id and row["availability"] == 1}


def build_default_data():
    """Wire AssistantData to the real services. Needs a Flask app context."""
    from database.connection import get_db_connection
    from employee_management.EmployeeRepository import EmployeeRepository
    from employee_management.EmployeeService import EmployeeService
    from availability.AvailabilityRepository import AvailabilityRepository
    from availability.AvailabilityService import AvailabilityService
    
    def with_service(call):
        connection = get_db_connection()
        try:
            employee_service = EmployeeService(EmployeeRepository(connection))
            availability_service = AvailabilityService(AvailabilityRepository(connection), employee_service)
            return call(employee_service, availability_service)
        finally:
            connection.close()

    return AssistantData(
        load_employees=lambda: with_service(lambda es, _: es.list_employees()),
        load_roles=lambda: with_service(lambda es, _: es.list_roles()),
        load_qualifications=lambda: with_service(
            lambda es, _: es.list_qualifications()),
        load_availability=lambda: with_service(lambda _, avs: avs.get_availability()),
    )
