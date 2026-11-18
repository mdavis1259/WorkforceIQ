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
from shared.exceptions import(
    InvalidCredentialsError,
    PermissionDeniedError
)


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

        if user is None:
            raise InvalidCredentialsError(
                "Invalid username or password."
            )

        if not user.active:
            raise PermissionDeniedError(
                "Account is disabled."
            )

        if not check_password_hash(user.password, password):
            raise InvalidCredentialsError(
                "Invalid username or password."
            )

        return user
    

    def get_user_by_user_id(self, userid):
        """
        Retrieve a user account.
        """
        return self.user_service.get_user_by_id(userid)
    
    def register(
        self,
        username,
        password_hash,
        system_role_id,
        employee_id,
    ):
        """
        Register a new WorkforceIQ user.

        Authentication coordinates the registration workflow
        but delegates ownership of user accounts to
        User Management.
        """
        user, _ = self.user_service.create_user(
            username=username,
            system_role_id=system_role_id,
            employee_id=employee_id,
            force_password_reset=True
        )
        return user