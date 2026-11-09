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
from user_management.User import User
from shared.exceptions import (
    ValidationError,
    NotFoundError,
    InvalidStateError
)

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
        Initialize the service with a UserRepository.

        Args:
            repository:
                Repository responsible for all Users table database operations.
        """
        self.repository = repository


    def get_user_by_id(self, userid):
        """
        Retrieve a user account by its unique ID.

        SDS Layer:
            Module Layer

        Args:
            userid:
                User account identifier.

        Returns:
            User account data or None if the user
            does not exist.
        """
        return self.repository.get_user_by_id(userid)


    def get_user_by_username(self, username):
        """
        Retrieve a user account by username.

        Authentication uses this method during
        login to locate the account associated
        with the submitted username.

        SDS Layer:
            Module Layer

        Args:
            username:
                Username supplied by the user.

        Returns:
            User account data or None if the
            username does not exist.
        """
        return self.repository.get_user_by_username(username)


    def list_users(self):
        """
        Retrieve all active user accounts.

        SDS Layer:
            Module Layer

        Returns:
            List of User contract objects.
        """
        return self.repository.list_users()


    def create_user(
        self,
        username,
        password,
        system_role_id,
        employee_id
    ):
        """
        Create a WorkforceIQ user account.

        SDS Layer:
            Module Layer

        Args:
            username:
                Unique account username.

            password:
                Password hash associated with the account.

            system_role_id:
                WorkforceIQ permission level assigned to the user.

            employee_id:
                Associated employee record.
            
        Returns:
            Newly-created User object.
        """
        if not username:
            raise ValidationError("Username is required.")
        
        if not password:
            raise ValidationError("Password is required.")

        if system_role_id not in (0, 1, 2, 3):
            raise ValidationError("Invalid system role.")

        if employee_id is None:
            raise ValidationError("Employee association is required.")

            # TODO (ARCH-1):
            # Verify employee_id exists once
            # EmployeeService is available.

        existing_user = self.get_user_by_username(username)

        if existing_user:
            raise ValidationError("Username already exists.")


        # Build the SDS 8.7 User contract object.
        #
        # Services create and validate business objects before sending
        # them to the repository layer.
        user = User(
            userid=None,
            username=username,
            password=password,
            system_role_id=system_role_id,
            employee_id=employee_id,
            active=True   
        )

        return self.repository.create_user(user)

    def update_user(self, user):
        """
        Update a user account.

        SDS Layer:
            Module Layer

        Args:
            user:
                User contract object containing updated account information.

        Returns:
            Updated User object.
        """      

        if user is None:
            raise ValidationError("User is required.")

        if not user.username:
            raise ValidationError("Username is required.")

        if user.system_role_id not in (0, 1, 2, 3):
            raise ValidationError("Invalid system role.")

        if user.employee_id is None:
            raise ValidationError("Employee association is required.")

        existing_user = self.get_user_by_id(user.userid)

        if existing_user is None:
            raise NotFoundError("User not found.")

        # UserRepository performs the actual database update.
        return self.repository.update_user(user)

    def change_role(self, userid, system_role_id):
        """
        Change a user's permission level.

        SDS Layer:
            Module Layer

        Args:
            userid:
                User account identifier.

            system_role_id:
                New system role identifier.

        Returns:
            Updated User object.
        """

        if system_role_id not in (0, 1, 2, 3):
            raise ValidationError("Invalid system role.")

        user = self.get_user_by_id(userid)

        if user is None:
            raise NotFoundError("User not found.")

        # User Management owns permissions.
        # Other modules must change permissions through UserService
        # rather than accessing the Users table directly.
        return self.repository.update_role(userid, system_role_id)

    def reset_password(self, userid, password_hash):
        """
        Reset a user's password.

        SDS Layer:
            Module Layer

        Args:
            userid:
                User account identifier.

            password_hash:
                Newly generated password hash.

        Returns:
            Updated User object.
        """

        if not password_hash:
            raise ValidationError("Password hash is required.")

        user = self.get_user_by_id(userid)

        if user is None:
            raise NotFoundError("User not found.")

        # Authentication may initiate password changes,
        # but User Management owns modification of user account data.
        return self.repository.reset_password(userid, password_hash)

    def deactivate_user(self, userid):
        """
        Deactivate a user account.

        SDS Layer:
            Module Layer

        Args:
            userid:
                User account identifier.

        Returns:
            Updated User object.
        """

        user = self.get_user_by_id(userid)

        if user is None:
            raise NotFoundError("User not found.")

        if not user.active:
            raise InvalidStateError("User is already inactive.")

        # User Management performs soft deletes.
        # Deactivated users remain in the database so historical
        # records remain valid.
        return self.repository.deactivate_user(userid)
    

