from flask import request, render_template, Blueprint
from flask_login import login_required
from ai_assistant.AssistantService import AssistantService

assistant_bp = Blueprint(
    "assistant",
    __name__,
    template_folder="templates"
)


@assistant_bp.route("/ai", methods=["GET", "POST"])
@login_required
def ai_assistant():
    response = ""

    if request.method == "POST":
        question = request.form["question"]
        employee_context = AssistantService.get_employee_context()

        prompt = f""" 
        You are WorkforceIQ, an AI workforce scheduling assistant.
        
        Use ONLY the employee information below.

        Do not invent employees.
        Do not invent wages.
        Do not invent roles.
        Do not invent schedules.

        {employee_context}
        
        Question:
        {question}
        """

        response = AssistantService.ask_ollama(prompt)
        
    return render_template("ai_assistant.html", response=response)
