import os
import sqlite3
import tempfile
import unittest

from user_management.User import User
from user_management.UserRepository import UserRepository
from user_management.UserService import UserService

from shared.exceptions import (
    ValidationError,
    NotFoundError,
    InvalidStateError
)


class UserManagementTests(unittest.TestCase):

    def setUp(self):

        self.temp_directory = tempfile.TemporaryDirectory()

        self.database_path = os.path.join(
            self.temp_directory.name,
            "users.db"
        )

        self.create_test_database()

        self.connection = sqlite3.connect(
            self.database_path
        )

        self.connection.row_factory = sqlite3.Row

        self.repository = UserRepository(
            self.connection
        )

        self.service = UserService(
            self.repository
        )

    def tearDown(self):

        self.connection.close()

        self.temp_directory.cleanup()

    def create_test_database(self):

        connection = sqlite3.connect(
            self.database_path
        )

        connection.executescript(
            """
            CREATE TABLE Users(
                userid INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                system_role_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            """
        )

        connection.execute(
            """
            INSERT INTO Users(
                username,
                password,
                system_role_id,
                employee_id,
                active
            )
            VALUES(
                'admin',
                'hash',
                3,
                100,
                1
            )
            """
        )

        connection.commit()
        connection.close()

    # ==================================
    # REPOSITORY TESTS
    # ==================================

    def test_get_user_by_id_returns_user(self):

        user = self.repository.get_user_by_id(1)

        self.assertEqual(
            user.username,
            "admin"
        )

    def test_get_user_by_username_returns_user(self):

        user = self.repository.get_user_by_username(
            "admin"
        )

        self.assertEqual(
            user.userid,
            1
        )

    def test_create_user_persists_user(self):

        user = User(
            userid=None,
            username="testuser",
            password="hash",
            system_role_id=1,
            employee_id=200
        )

        created_user = (
            self.repository.create_user(user)
        )

        self.assertEqual(
            created_user.username,
            "testuser"
        )

    def test_list_users_returns_active_users(self):

        users = self.repository.list_users()

        self.assertEqual(
            len(users),
            1
        )

    def test_update_role_updates_system_role(self):

        updated_user = (
            self.repository.update_role(
                1,
                2
            )
        )

        self.assertEqual(
            updated_user.system_role_id,
            2
        )

    def test_reset_password_updates_password_hash(self):

        updated_user = (
            self.repository.reset_password(
                1,
                "newhash"
            )
        )

        self.assertEqual(
            updated_user.password,
            "newhash"
        )

    def test_deactivate_user_sets_active_false(self):

        updated_user = (
            self.repository.deactivate_user(
                1
            )
        )

        self.assertFalse(
            updated_user.active
        )

    # ==================================
    # SERVICE TESTS
    # ==================================

    def test_create_user_requires_username(self):

        with self.assertRaises(
            ValidationError
        ):
            self.service.create_user(
                "",
                "hash",
                1,
                100
            )

    def test_create_user_requires_password(self):

        with self.assertRaises(
            ValidationError
        ):
            self.service.create_user(
                "newuser",
                "",
                1,
                100
            )

    def test_create_user_requires_employee_id(self):

        with self.assertRaises(
            ValidationError
        ):
            self.service.create_user(
                "newuser",
                "hash",
                1,
                None
            )

    def test_create_user_rejects_invalid_role(self):

        with self.assertRaises(
            ValidationError
        ):
            self.service.create_user(
                "newuser",
                "hash",
                99,
                100
            )

    def test_create_user_rejects_duplicate_username(self):

        with self.assertRaises(
            ValidationError
        ):
            self.service.create_user(
                "admin",
                "hash",
                1,
                100
            )

    def test_change_role_updates_role(self):

        updated_user = (
            self.service.change_role(
                1,
                2
            )
        )

        self.assertEqual(
            updated_user.system_role_id,
            2
        )

    def test_change_role_rejects_missing_user(self):

        with self.assertRaises(
            NotFoundError
        ):
            self.service.change_role(
                999,
                2
            )

    def test_deactivate_user_rejects_missing_user(self):

        with self.assertRaises(
            NotFoundError
        ):
            self.service.deactivate_user(
                999
            )

    def test_deactivate_user_rejects_already_inactive_user(self):

        self.service.deactivate_user(1)

        with self.assertRaises(
            InvalidStateError
        ):
            self.service.deactivate_user(1)


if __name__ == "__main__":
    unittest.main()