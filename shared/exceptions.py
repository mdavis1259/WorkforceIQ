"""
WorkforceIQ Custom Exceptions

Per SDS 8.6 and 8.8, Services raise
business exceptions and Routes convert
them into HTTP responses.


API Routes (blueprints) turn these into the HTTP errors in SDS section 8.8:
    ValidationError -> 400 VALIDATION_ERROR
    InvalidCredentialsError -> 401 INVALID_CREDENTIALS
    PermissionDeniedError -> 403 FORBIDDEN
    NotFoundError   -> 404 NOT_FOUND
    ConflictError -> 409 CONFLICT
    InvalidStateError -> 409 INVALID_STATE
    RuleViolationError -> 409 RULE_VIOLATION
    InsufficientHistoryError -> 422 INSUFFICIENT_HISTORY
"""

class ValidationError(Exception):
    """Input is missing, badly formatted, or out of range.

    details is a list of {"field": ..., "issue": ...} dictionaries so the
    API can return every problem at once.
    """

    def __init__(self, details):
        if isinstance(details, str):
            self.details = []
            message = details
        else:
            self.details = list(details)
            message = "; ".join(f"{d['field']}: {d['issue']}" for d in self.details)
        super().__init__(message or "Validation failed.")

class InvalidCredentialsError(Exception):
    """Username or password is invalid."""
    pass

class PermissionDeniedError(Exception):
    """User lacks required permission."""
    pass

class NotFoundError(Exception):
    """A requested record does not exist."""
    pass

class ConflictError(Exception):
    """Requested operation conflicts with system state."""
    pass

class InvalidStateError(Exception):
    """Resource is in an invalid state for the operation."""
    pass

class RuleViolationError(Exception):
    """Scheduling operation violates one or more business rules."""
    pass

class InsufficientHistoryError(Exception):
    """Forecasting has fewer than 8 weeks of historical data."""

    def __init__(self, details=None):
        super().__init__("Not enough data to process the request.")

        self.error = True
        self.code = "INSUFFICIENT_HISTORY"
        self.message = "Not enough data to process the request."
        self.details = details or {}
