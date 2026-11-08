"""
Authentication Repository

Under architectural review.

The SDS currently assigns ownership of:
    USERS
    SYSTEM_ROLES

to Authentication.

However, User Management now owns user
account CRUD operations through
UserRepository and UserService.

This repository will remain as a placeholder
until final ownership boundaries are approved
by the team.
"""

# SDS Note:
#
# Section 4.1 assigns user accounts and
# permissions to User Management.
#
# Section 8.9 assigns USERS to Authentication.
#
# Ownership is currently under review.

class AuthRepository:
    pass