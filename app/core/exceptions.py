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
