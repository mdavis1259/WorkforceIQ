"""
Authentication Repository

Per the WorkforceIQ SDS, only repository classes contain SQL.

The Authentication repository is responsible for database
operations owned by the Authentication module, including:

    - Registration support
    - Authentication-related lookups
    - System role management

Routes and services must never execute SQL directly.
All database access must be performed through repository
methods.

Architecture:

    Routes
      ↓
    Services
      ↓
    Repositories
      ↓
    SQLite
"""


class AuthRepository:
    """
    Provides Authentication module access to
    authentication-related database records.

    This repository will support Registration,
    Login, Logout, Session Management, and
    Role Checks as defined by the SDS.
    """

    def __init__(self, conn):
        """
        Initialize the repository with an
        active database connection.

        Args:
            conn:
                SQLite database connection.
        """
        self.conn = conn

    def get_role_by_name(self, role_name):
        """
        Retrieve a system role by name.

        Used during registration and account
        creation workflows to determine the
        appropriate permission level.

        Args:
            role_name:
                Name of the requested role.

        Returns:
            Role data if found; otherwise None.
        """
        raise NotImplementedError

    def create_role(self, role_data):
        """
        Create a new system role.

        Intended for administrative and
        registration workflows when a required
        role does not already exist.

        Args:
            role_data:
                Information required to create
                the role.

        Returns:
            Newly created role information.
        """
        raise NotImplementedError

    def create_user(self, user_data):
        """
        Create a new user account.

        Registration is owned by the
        Authentication module; however,
        user-account CRUD ultimately belongs
        to the User Management module.

        Future implementation should be
        reviewed with the team to clarify
        responsibility boundaries between
        Authentication and User Management.

        Args:
            user_data:
                User account information.

        Returns:
            Newly created user account.
        """
        raise NotImplementedError


# TODO (SDS Review):
#
# Clarify ownership between Authentication
# and User Management.
#
# Current interpretation:
#
# Authentication owns:
#   - Registration workflow
#   - Login
#   - Logout
#   - Sessions
#   - Role checks
#
# User Management owns:
#   - User accounts
#   - Permissions
#   - User CRUD operations
#
# Registration may remain in Authentication
# while delegating user-account creation to
# the User Management module.