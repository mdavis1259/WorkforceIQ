"""
User Management Routes

Per the WorkforceIQ SDS, the User Management module
owns:

    - User accounts
    - Permissions

Authentication owns:

    - Login
    - Logout
    - Registration
    - Sessions
    - Role checks

User Management owns administration of user
accounts and permissions.
"""

from flask import (
    Blueprint,
    jsonify,
    request,
    render_template
)

from flask_login import (
    login_required,
    current_user
)

from shared.exceptions import (
    ValidationError,
    NotFoundError,
    InvalidStateError,
    PermissionDeniedError
)

from database.connection import get_db_connection
from user_management.UserRepository import UserRepository
from user_management.UserService import UserService

# =====================================================
# USER MANAGEMENT BLUEPRINT
# =====================================================

user_bp = Blueprint(
    "user",
    __name__,
    template_folder="templates"
)


# =====================================================
# HELPERS
# =====================================================

# SDS Role Definitions:
# 1 = Employee
# 2 = Manager
# 3 = Administrator
ADMINISTRATOR_ROLE_ID = 3

def _require_administrator():
    """
    Ensure the current user has Administrator
    privileges.
    """

    if current_user.system_role_id != ADMINISTRATOR_ROLE_ID:
        raise PermissionDeniedError(
            "Administrator access required."
        )
    

def _build_user_service():

    conn = get_db_connection()

    repository = UserRepository(conn)

    service = UserService(repository)

    return service, conn


def _user_response(user):
    """
    Convert a User contract object into an
    API response payload.
    """

    return {
        "userid": user.userid,
        "username": user.username,
        "system_role_id": user.system_role_id,
        "employee_id": user.employee_id,
        "active": user.active
    }


@user_bp.route("/users")
@login_required
def users():
    
    service, conn = _build_user_service()

    try:

        _require_administrator

        users = service.list_users()

        return render_template(
            "users.html",
            users=users
        )

    finally:
        if conn:
            conn.close()

# =====================================================
# GET /api/users
# =====================================================

@user_bp.route(
    "/api/users",
    methods=["GET"]
)
@login_required
def list_users():
    """
    Return all active user accounts.
    """

    service, conn = _build_user_service()

    try:

        _require_administrator()

        users = service.list_users()

        return jsonify(
            [
                _user_response(user)
                for user in users
            ]
        ), 200

    except PermissionDeniedError as ex:

        return jsonify(
            {
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(ex)
                }
            }
        ), 403

    finally:
        if conn:
            conn.close()


# =====================================================
# POST /api/users
# =====================================================

@user_bp.route(
    "/api/users",
    methods=["POST"]
)
@login_required
def create_user():
    """
    Create a new user account.
    """

    service, conn = _build_user_service()

    try:

        _require_administrator()

        data = request.get_json() or {}

        user = service.create_user(
            username=data.get("username"),
            password=data.get("password"),
            system_role_id=data.get("system_role_id"),
            employee_id=data.get("employee_id")
        )

        return jsonify(
            _user_response(user)
        ), 201

    except ValidationError as ex:

        return jsonify(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(ex)
                }
            }
        ), 400

    except InvalidStateError as ex:

        return jsonify(
            {
                "error": {
                    "code": "INVALID_STATE",
                    "message": str(ex)
                }
            }
        ), 409

    except PermissionDeniedError as ex:

        return jsonify(
            {
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(ex)
                }
            }
        ), 403

    finally:
        if conn:
            conn.close()


# =====================================================
# PATCH /api/users/<userid>
# =====================================================

@user_bp.route(
    "/api/users/<int:userid>",
    methods=["PATCH"]
)
@login_required
def update_user(userid):
    """
    Update user permissions, account status,
    or credentials.
    """

    service, conn = _build_user_service()

    try:

        _require_administrator()

        data = request.get_json() or {}

        if "system_role_id" in data:

            user = service.change_role(
                userid,
                data["system_role_id"]
            )

        elif "password_hash" in data:

            user = service.reset_password(
                userid,
                data["password_hash"]
            )

        elif (
            "active" in data and
            data["active"] is False
        ):

            user = service.deactivate_user(
                userid
            )

        else:

            return jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message":
                            "No supported update supplied."
                    }
                }
            ), 400

        return jsonify(
            _user_response(user)
        ), 200

    except ValidationError as ex:

        return jsonify(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(ex)
                }
            }
        ), 400

    except NotFoundError as ex:

        return jsonify(
            {
                "error": {
                    "code": "NOT_FOUND",
                    "message": str(ex)
                }
            }
        ), 404

    except InvalidStateError as ex:

        return jsonify(
            {
                "error": {
                    "code": "INVALID_STATE",
                    "message": str(ex)
                }
            }
        ), 409

    except PermissionDeniedError as ex:

        return jsonify(
            {
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(ex)
                }
            }
        ), 403

    finally:
        if conn:
            conn.close()
