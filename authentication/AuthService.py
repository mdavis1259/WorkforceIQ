"""
Authentication Service

Per the WorkforceIQ SDS, the Authentication module is
responsible for:

    - Registration
    - Login
    - Logout
    - Session management
    - Role checks

This service contains the business rules used to
authenticate users and coordinate registration and
authorization workflows.

Following the WorkforceIQ architecture:

    Routes
      ↓
    AuthService
      ↓
    Other Services
      ↓
    Repositories

Authentication does not access database tables directly.
User account information is obtained through the
User Management module.
"""

from werkzeug.security import check_password_hash
from user_management.UserService import UserService


class AuthService:
    """
    Provides Authentication business logic.

    This service verifies user credentials and
    coordinates authentication workflows while
    relying on User Management to provide user
    account data.
    """

    def __init__(self, user_service):
        """
        Initialize the service with access to
        the User Management module.

        Args:
            user_service:
                UserService instance used to
                retrieve user account information.
        """
        self.user_service = user_service

    def authenticate(self, username, password):
        """
        Authenticate a user using a username
        and password.

        Authentication validates the supplied
        credentials against the user account
        managed by User Management.

        Args:
            username:
                Username supplied during login.

            password:
                Plain-text password supplied
                during login.

        Returns:
            User account data if authentication
            succeeds; otherwise None.
        """

        user = self.user_service.get_user_by_username(
            username
        )

        if not user:
            return None

        if check_password_hash(
            user["password"],
            password
        ):
            return user

        return None

    def get_user_by_user_id(self, user_id):
        """
        Retrieve a user account.

        TODO:
        Determine ownership with the project team.

        The SDS currently lists get_user() under
        AuthService, but the User Management module
        owns user accounts and permissions.
        """

        raise NotImplementedError

    def create_user(self, data):
        """
        Create a new user account as part of the
        registration workflow.

        TODO:
        Clarify responsibility boundaries between
        Authentication and User Management.

        Current architectural direction:

            Authentication:
                - Registration workflow
                - Login
                - Logout
                - Sessions
                - Role checks

            User Management:
                - User account CRUD
                - Permissions
                - Role administration

        Authentication should orchestrate the
        registration process while delegating
        user-account creation to User Management.
        """

        raise NotImplementedError