# Error aplikasi bebas framework, supaya boleh di-raise dari layer domain & application.
# Pemetaan ke HTTP status ada di app/core/error_handlers.py.


class AppError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class BadRequestError(AppError):
    pass


class UnauthorizedError(AppError):
    pass


class ForbiddenError(AppError):
    pass


class NotFoundError(AppError):
    pass


class ConflictError(AppError):
    pass
