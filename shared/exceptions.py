"""
WorkforceIQ Custom Exceptions

Per SDS 8.6 and 8.8, Services raise
business exceptions and Routes convert
them into HTTP responses.
"""


class ValidationError(Exception):
    """Input failed validation."""
    pass


class NotFoundError(Exception):
    """Requested resource does not exist."""
    pass


class PermissionDeniedError(Exception):
    """User lacks required permission."""
    pass


class ConflictError(Exception):
    """Requested operation conflicts with system state."""
    pass


class InvalidStateError(Exception):
    """Resource is in an invalid state for the operation."""
    pass

class InvalidCredentialsError(Exception):
    """Username or password is invalid."""
    pass

class RuleViolationError(Exception):
    """Scheduling operation violates one or more business rules."""
    pass
