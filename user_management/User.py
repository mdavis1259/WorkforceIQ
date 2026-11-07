from flask_login import UserMixin


class User(UserMixin):
    """
    User Management domain object.

    Represents a WorkforceIQ user account and its associated
    permissions within the system.

    Per the SDS, user accounts are owned by the User Management
    module and are linked to Employee records. Authentication
    uses these accounts to perform login, session management,
    and role-based access control.
    """

    def __init__(
        self,
        userid,
        username,
        system_role_id,
        employee_id=None
    ):
        """
        Create a User account object.

        Args:
            userid:
                Unique identifier from the Users table.

            username:
                Username used to authenticate and identify
                the user within WorkforceIQ.

            system_role_id:
                System permission level assigned to the user.
                Determines which application features the
                user may access.

            employee_id:
                Associated employee record. The SDS requires
                each user account to be linked to an employee
                so access can be restricted to the user's own
                availability, schedules, and requests when
                appropriate.
        """

        # Flask-Login identifier for the current session.
        self.id = userid

        # Unique user account identifier.
        self.userid = userid

        # Authentication username.
        self.username = username

        # Authorization level used for role checks.
        self.system_role_id = system_role_id

        # Linked Employee record.
        self.employee_id = employee_id