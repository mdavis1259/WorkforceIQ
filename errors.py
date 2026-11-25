"""Shared exception types (SDS section 8.6).

Routes (blueprints) turn these into the HTTP errors in SDS section 8.8:
    ValidationError -> 400 VALIDATION_ERROR
    NotFoundError   -> 404 NOT_FOUND
"""



class NotFoundError(Exception):
    """A requested record does not exist."""


class ValidationError(Exception):
    """Input is missing, badly formatted, or out of range.

    details is a list of {"field": ..., "issue": ...} dictionaries so the
    API can return every problem at once.
    """

    def __init__(self, details):
        self.details = list(details)
        message = "; ".join(f"{d['field']}: {d['issue']}" for d in self.details)
        super().__init__(message or "Validation failed.")

class InsufficientHistoryError(Exception):
    """Forecasting has fewer than 8 weeks of historical data."""

    def __init__(self, details=None):
        super().__init__("Not enough data to process the request.")

        self.error = True
        self.code = "INSUFFICIENT_HISTORY"
        self.message = "Not enough data to process the request."
        self.details = details or {}

        
