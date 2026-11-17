from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from assistant.Controller import Controller
from shared.exceptions import PermissionDeniedError, ValidationError

ai_bp = Blueprint("assistant", __name__, template_folder="templates")
controller = Controller()


def _error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def _question():
    body = request.get_json(silent=True)
    if isinstance(body, dict):
        return body.get("question", "")
    return request.form.get("question", "")


# GET/POST /ai  (the page)
@ai_bp.route("/ai", methods=["GET", "POST"])
@login_required
def ai_assistant():
    response, error = None, None
    if request.method == "POST":
        try:
            response = controller.query(_question())
        except (ValidationError, PermissionDeniedError) as problem:
            error = str(problem)
    return render_template("ai_assistant.html", response=response, error=error)


# POST /api/assistant/query
@ai_bp.route("/api/assistant/query", methods=["POST"])
@login_required
def query():
    try:
        return jsonify(controller.query(_question()))
    except PermissionDeniedError as problem:
        return _error("PERMISSION_DENIED", str(problem), 403)
    except ValidationError as problem:
        return _error("VALIDATION_ERROR", str(problem), 400)


# GET /api/assistant/health
@ai_bp.route("/api/assistant/health", methods=["GET"])
@login_required
def health():
    return jsonify(controller.health())
