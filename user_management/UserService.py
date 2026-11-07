"""
User Management Service

Per the WorkforceIQ SDS, the User Management module is
responsible for user accounts and permissions.

This service contains business logic related to user
accounts and acts as the interface between routes and
the UserRepository.

Following the WorkforceIQ architecture:

    Routes
      ↓
    UserService
      ↓
    UserRepository

Routes must not access the database directly.
All SQL belongs in the repository layer.
"""


class UserService:
    """
    Provides user account operations for the
    User Management module.

    Other modules should access user-account data
    through this service rather than querying the
    Users table directly.
    """

    def __init__(self, repository):
        """
        Initialize the service with a repository.

        Args:
            repository:
                Repository responsible for all
                Users table database operations.
        """
        self.repository = repository

    def get_user(self, user_id):
        """
        Retrieve a user account by its unique ID.

        Used when a module needs information about
        a specific WorkforceIQ user account.

        Args:
            user_id:
                User account identifier.

        Returns:
            User account data or None if the user
            does not exist.
        """
        return self.repository.get_user_by_id(user_id)

    def get_user_by_username(self, username):
        """
        Retrieve a user account by username.

        Authentication uses this method during
        login to locate the account associated
        with the submitted username.

        Args:
            username:
                Username supplied by the user.

        Returns:
            User account data or None if the
            username does not exist.
        """
        return self.repository.get_user_by_username(username)

    # TODO (ARCH-1B):
    # Implement user-account management methods:
    #
    #   create_user(data)
    #   update_user(user_id, data)
    #   deactivate_user(user_id)
    #   change_role(user_id, role_id)
    #   reset_password(user_id)
    #
    # SDS ownership:
    #   User Management Module
    #       - User accounts
    #       - Permissions
    #
    # Authentication may call these methods as part
    # of the registration workflow, but User Management
    # remains the owner of user-account CRUD operations.