from __future__ import annotations

from typing import Any, Dict, Optional


class MuxiError(Exception):
    def __init__(self, code: str, message: str, status_code: int, details: Optional[Dict[str, Any]] = None):
        super().__init__(f"{code}: {message}" if code else message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AuthenticationError(MuxiError):
    pass


class AuthorizationError(MuxiError):
    pass


class NotFoundError(MuxiError):
    pass


class ConflictError(MuxiError):
    pass


class ValidationError(MuxiError):
    pass


class RateLimitError(MuxiError):
    def __init__(self, message: str, status_code: int, retry_after: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__("RATE_LIMITED", message, status_code, details)
        self.retry_after = retry_after


class ServerError(MuxiError):
    pass


class ConnectionError(MuxiError):
    pass


def map_error(status: int, code: str, message: str, details: Optional[Dict[str, Any]] = None, retry_after: Optional[int] = None) -> MuxiError:
    if status == 401:
        return AuthenticationError(code or "UNAUTHORIZED", message, status, details)
    if status == 403:
        return AuthorizationError(code or "FORBIDDEN", message, status, details)
    if status == 404:
        return NotFoundError(code or "NOT_FOUND", message, status, details)
    if status == 409:
        return ConflictError(code or "CONFLICT", message, status, details)
    if status == 422:
        return ValidationError(code or "VALIDATION_ERROR", message, status, details)
    if status == 429:
        return RateLimitError(message or "Too Many Requests", status, retry_after=retry_after, details=details)
    if status >= 500:
        return ServerError(code or "SERVER_ERROR", message, status, details)
    return MuxiError(code or "ERROR", message, status, details)
