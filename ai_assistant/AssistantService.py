import requests

from database.connection import get_db_connection
from employee_management.EmployeeRepository import EmployeeRepository
from employee_management.EmployeeService import EmployeeService


class AssistantService:

    def get_employee_context():
        # Reads employees through EmployeeService (SDS 8.6) instead of
        # calling our own /api/employees over HTTP.
        connection = get_db_connection()
        try:
            service = EmployeeService(EmployeeRepository(connection))
            employees = service.list_employees()
            role_names = {role["role_id"]: role["role_name"]
                          for role in service.list_roles()}
        finally:
            connection.close()
        context = "Current Employees:\n\n"
        for employee in employees:
            context += (
                f"Name: {employee.first_name.strip() + ' ' + employee.last_name.strip()}, "
                f"Role: {role_names.get(employee.role_id)}, "
                f"Wage: ${employee.hourly_rate}/hr\n"
            )
        print("Employee Context:\n" + context) #TODO: Remove this debug print statement in production
        return context
            


    def ask_ollama(prompt):
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False
            }
        )

        data = response.json()

        if "response" in data:
            return data["response"]

        if "error" in data:
            return f"Error: {data['error']}"

        return "Unknown response received."

