from flask import (
    Blueprint,
    render_template
)

from flask_login import login_required

from database.connection import get_db_connection

from scheduling.SchedulingRepository import (
    SchedulingRepository
)

from scheduling.SchedulingService import (
    SchedulingService
)

scheduling_bp = Blueprint(
    "scheduling",
    __name__,
    template_folder="templates"
)

def _build_scheduling_service():

    conn = get_db_connection()

    repository = SchedulingRepository(conn)

    service = SchedulingService(repository)

    return service, conn

@scheduling_bp.route("/shift_management")
@login_required
def shift_management():

    service, conn = _build_scheduling_service()

    try:

        shifts = service.list_shifts()

        requirements = (
            service.list_staffing_requirements()
        )

        return render_template(
            "shift_management.html",
            shifts=shifts,
            requirements=requirements
        )

    finally:
        conn.close()
        