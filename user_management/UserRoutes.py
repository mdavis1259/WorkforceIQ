"""
User Management Routes

Per the WorkforceIQ SDS, the User Management module is responsible for:

    - User accounts
    - Permissions

Authentication owns login, logout, registration,
sessions, and role checks.

User Management owns user account administration
and permission management.

Future User Management functionality will be exposed
through API endpoints such as:

    GET    /api/users
    POST   /api/users
    PATCH  /api/users/<user_id>

These endpoints are defined in the SDS but have not
yet been implemented.
"""

from flask import Blueprint


# =====================================================
# USER MANAGEMENT BLUEPRINT
# =====================================================

user_bp = Blueprint(
    "user",
    __name__,
    template_folder="templates"
)


# =====================================================
# FUTURE USER MANAGEMENT ROUTES
# =====================================================

# TODO (ARCH-1B):
#
# Create a User Management page for Administrators.
#
# Planned functionality:
#   - View all user accounts
#   - Create user accounts
#   - Assign and modify roles
#   - Enable/disable accounts
#   - Reset passwords
#   - Manage permissions
#
# SDS Reference:
#   User Management Module
#       - User accounts
#       - Permissions
#
# Planned API endpoints:
#   GET    /api/users
#   POST   /api/users
#   PATCH  /api/users/<user_id>
#
# Each route should follow the WorkforceIQ architecture:
#
#   Routes
#     ↓
#   UserService
#     ↓
#   UserRepository
#
# Routes should contain request/response handling only.
# Business rules belong in UserService.
# SQL belongs in UserRepository.