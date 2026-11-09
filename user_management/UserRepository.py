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
from user_management.User import User


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

    def _build_user(self, row):
        """
        SDS 8.7 Data Contract Mapper

        Converts a SQLite row into the User contract
        object exchanged between Services and Repositories.
        
        SQLite Row
            ↓
        User Contract
        """
        return User(
            userid=row["userid"],
            username=row["username"],
            password=row["password"],
            system_role_id=row["system_role_id"],
            employee_id=row["employee_id"],
            active=row["active"]
        )

    def create_user(self, user):
        """
        Persist a new User account to the database.

        SDS Layer:
            Data Layer

        Args:
            user:
                User data contract object supplied by
                UserService.

        Returns:
            Newly-created User object loaded from the
            database.
        """

        cursor = self.conn.cursor()

        # Translate the User contract object into a 
        # Users table record.
        cursor.execute("""
            INSERT INTO Users(
                username,
                password,
                system_role_id,
                employee_id,
                active
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user.username,
                user.password,
                user.system_role_id,
                user.employee_id,
                int(user.active)
            )
        )

        # Persist the new record.
        self.conn.commit()

        # Reload the record and return a complete
        # User contract object.
        return self.get_user_by_id(cursor.lastrowid)

    def get_user_by_id(self, userid):
        """
        Retrieve a user account by its unique ID.

        Used when a specific WorkforceIQ account
        must be loaded, such as during session
        restoration or account administration.

        SDS Layer:
            Data Layer

        Args:
            userid:
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
            (userid,)
        )

        row = cursor.fetchone()

        if row is None:
            return None

        # Convert the database row into a User
        # contract object before returning it to
        # the Service Layer.
        return self._build_user(row)
        

    def get_user_by_username(self, username):
        """
        Retrieve a user account by username.

        Used by the Authentication module during
        login and registration workflows.

        User Management owns the user-account data,
        while Authentication consumes that data
        through service interfaces.

        SDS Layer:
            Data Layer

        Args:
            username:
                Username supplied by the user.

        Returns:
            User record if found; otherwise None.
        """

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM Users
            WHERE username = ?
            """,
            (username,)
        )

        row = cursor.fetchone()

        if row is None:
            return None

        # Convert the database row into a User
        # contract object before returning it to
        # the Service layer.
        return self._build_user(row)    

    def list_users(self):
        """
        Retrieve all active user accounts.

        SDS Layer:
            Data Layer

        Returns:
            List of User contract objects.
        """
        
        cursor = self.conn.cursor()

        # Retrieve active users only.
        #
        # WorkforceIQ uses soft deletes, so inactive
        # users remain in the database for auditing
        # and historical record retention.
        cursor.execute(
            """
            SELECT *
            FROM Users
            WHERE active = 1
            ORDER BY username
            """
        )

        rows = cursor.fetchall()

        users = []

        # Convert database rows into User contract
        # objects before returning data to the
        # Service Layer.
        for row in rows:
            users.append(self._build_user(row))

        return users

    def update_user(self, user):
        """
        Update an existing user account.

        SDS Layer:
            Data Layer

        Args:
            user:
                User contract object containing
                updated account information.

        Returns:
            Updated User object.
        """

        cursor = self.conn.cursor()

        # Translate updated User contract object
        # into Users table columns.
        cursor.execute(
            """
            UPDATE Users
            SET
                username = ?,
                password = ?,
                system_role_id = ?,
                employee_id = ?,
                active = ?
            WHERE userid = ?
            """,
            (
                user.username,
                user.password,
                user.system_role_id,
                user.employee_id,
                int(user.active),
                user.userid
            )
        )

        self.conn.commit()

        # Reload the updated account and return
        # a fresh User contract object.
        return self.get_user_by_id(user.userid)

    def deactivate_user(self, userid):
        """
        Deactivate a user account.

        SDS Layer:
            Data Layer

        Args:
            userid:
                Unique identifier of the user account being deactivated.
        
        Returns:
            Updated User object.
        """

        cursor = self.conn.cursor()

        # WorkforceIQ uses soft deletes for user
        # accounts to preserve historical records,
        # schedules, and auditability.
        cursor.execute(
            """
            UPDATE Users
            SET active = 0
            WHERE userid = ?
            """,
            (userid,)
        )

        self.conn.commit()

        return self.get_user_by_id(userid)

    def update_role(self, userid, system_role_id):
        """
        Update the user's system role.

        SDS Layer:
            Data Layer

        Args:
            userid:
                User account identifier.

            system_role_id:
                New system role identifier.

        Returns:
            Updated User object if successful;
            otherwise None.
        """

        cursor = self.conn.cursor()

        # User Management owns permissions per
        # SDS Section 4.1. Updating the system
        # role changes the user's access level.
        cursor.execute(
            """
            UPDATE Users
            SET system_role_id = ?
            WHERE userid = ?
            """,
            (
                system_role_id,
                userid
            )
        )

        self.conn.commit()

        return self.get_user_by_id(userid)
    

    def reset_password(self, userid, password_hash):
        """
        Update a user's password hash.

        SDS Layer:
            Data Layer

        Args:
            userid:
                Unique identifier of the user account whose
                password is being updated.

            password_hash:
                Newly generated password hash that will replace
                existing stored hash.

        Returns:
            Updated User object.
        """

        cursor = self.conn.cursor()

        # Authentication may initiate password
        # changes, but User Management owns storage
        # of user account credentials.
        cursor.execute(
            """
            UPDATE Users
            SET password = ?
            WHERE userid = ?
            """,
            (
                password_hash,
                userid
            )
        )

        self.conn.commit()

        return self.get_user_by_id(userid)
    