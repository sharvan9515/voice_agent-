from __future__ import annotations


class AppError(Exception):
    status_code: int = 500
    message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None, status_code: int | None = None) -> None:
        self.message = message or self.__class__.message
        self.status_code = status_code or self.__class__.status_code
        super().__init__(self.message)


class ValidationError(AppError):
    status_code = 400
    message = "Validation error"


class UnauthorizedError(AppError):
    status_code = 401
    message = "Unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    message = "Forbidden"


class NotFoundError(AppError):
    status_code = 404
    message = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    message = "Resource conflict"


class ExternalServiceError(AppError):
    status_code = 502
    message = "External service error"
