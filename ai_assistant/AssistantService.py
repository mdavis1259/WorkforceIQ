class AssistantService:

    def get_employee_context():
        employees = requests.get("http://127.0.0.1:5000/api/employees").json()
        context = "Current Employees:\n\n"
        for employee in employees:
            context += (
                f"Name: {employee['first_name'].strip() + ' ' + employee['last_name'].strip()}, "
                f"Role: {employee['role']}, "
                f"Wage: ${employee['hourly_rate']}/hr\n"
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

