"""
User Management Repository

Per the WorkforceIQ SDS, repositories are responsible
for all database access and contain the SQL used by
their module.

The User Management module owns:

    - User accounts
    - Permissions

Other modules must access user account data through
UserService rather than querying the Users table
directly.

Architecture:

    Routes
      ↓
    Services
      ↓
    Repositories
      ↓
    SQLite

All SQL related to user accounts should be placed in
this repository.
"""


class UserRepository:
    """
    Provides database access for User Management.

    Responsible for retrieving and maintaining data
    stored in the Users table.
    """

    def __init__(self, conn):
        """
        Initialize the repository with an active
        database connection.

        Args:
            conn:
                SQLite database connection.
        """
        self.conn = conn

    def get_user_by_id(self, user_id):
        """
        Retrieve a user account by its unique ID.

        Used when a specific WorkforceIQ account
        must be loaded, such as during session
        restoration or account administration.

        Args:
            user_id:
                Unique identifier from the Users table.

        Returns:
            User record if found; otherwise None.
        """

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM Users
            WHERE userid = ?
            """,
            (user_id,)
        )

        return cursor.fetchone()

    def get_user_by_username(self, username):
        """
        Retrieve a user account by username.

        Used by the Authentication module during
        login and registration workflows.

        User Management owns the user-account data,
        while Authentication consumes that data
        through service interfaces.

        Args:
            username:
                Username supplied by the user.

        Returns:
            User record if found; otherwise None.
        """

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT
                userid,
                username,
                password,
                system_role_id,
                employee_id
            FROM Users
            WHERE username = ?
            """,
            (username,)
        )

        return cursor.fetchone()

    # TODO (ARCH-1B):
    #
    # Add user-account CRUD operations:
    #
    #   create_user(data)
    #   update_user(user_id, data)
    #   deactivate_user(user_id)
    #   update_role(user_id, role_id)
    #   reset_password(user_id)
    #
    # These methods will support the User
    # Management API defined in the SDS:
    #
    #   GET    /api/users
    #   POST   /api/users
    #   PATCH  /api/users/{user_id}
    #
    # Authentication may call these methods as
    # part of the registration workflow, but
    # User Management remains the owner of
    # user-account data and permissions.