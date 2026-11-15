from flask import request, render_template, Blueprint, jsonify
from flask_login import login_required
from assistant.Controller import Controller


# Register the AI Blueprint
ai_bp = Blueprint(
    "assistant",
    __name__,
    template_folder="templates"
)

# Instantiate the Controller
controller = Controller()

# GET /ai
@ai_bp.route("/ai", methods=["GET", "POST"])
@login_required
def ai_assistant():

    response = None

    if request.method == "POST":

        controller = Controller()

        response = controller.query(request)

    return render_template(
        "ai_assistant.html", response=response
    )

# POST /api/assistant/query
@ai_bp.route("/api/assistant/query", methods=["POST"])
@login_required
def query():

    response =  controller.query(request)

    return jsonify(response)

# GET /api/assistant/health
@ai_bp.route("/api/assistant/health", methods=["GET"])
@login_required
def health():

    return controller.health()



