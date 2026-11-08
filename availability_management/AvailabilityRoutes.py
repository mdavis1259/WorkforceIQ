from flask import Blueprint

availability_bp = Blueprint(
    "availability",
    __name__,
    template_folder="templates"
)