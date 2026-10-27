from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AppError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)

_STATUS_CODES: dict[type[AppError], int] = {
    BadRequestError: 400,
    UnauthorizedError: 401,
    ForbiddenError: 403,
    NotFoundError: 404,
    ConflictError: 409,
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        status_code = next(
            (_STATUS_CODES[cls] for cls in type(exc).__mro__ if cls in _STATUS_CODES),
            400,
        )
        return JSONResponse(status_code=status_code, content={"detail": exc.message})
