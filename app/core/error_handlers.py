from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    AppError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)

_STATUS_CODES: dict[type[AppError], int] = {
    BadRequestError: 400,
    UnauthorizedError: 401,
    ForbiddenError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    ServiceUnavailableError: 503,
}

_HTTP_MESSAGES: dict[int, str] = {
    401: "Silakan login terlebih dahulu",
    403: "Anda tidak memiliki akses ke fitur ini",
    404: "Endpoint tidak ditemukan",
    405: "Metode HTTP tidak diizinkan untuk endpoint ini",
}

_VALIDATION_MESSAGES: dict[str, str] = {
    "missing": "Wajib diisi",
    "string_type": "Harus berupa teks",
    "bool_type": "Harus berupa true atau false",
    "bool_parsing": "Harus berupa true atau false",
    "int_type": "Harus berupa angka bulat",
    "int_parsing": "Harus berupa angka bulat",
    "json_invalid": "Format JSON tidak valid",
    "model_attributes_type": "Body harus berupa objek JSON",
    "dict_type": "Body harus berupa objek JSON",
}

_LOCATION_PREFIXES = {"body", "query", "path", "header", "cookie"}


def _error_content(
    message: str,
    errors: list[dict[str, str]] | None = None,
    code: str | None = None,
) -> dict[str, Any]:
    content: dict[str, Any] = {"success": False, "message": message, "data": None}
    if errors is not None:
        content["errors"] = errors
    if code is not None:
        content["code"] = code
    return content


def _field_name(error: dict[str, Any]) -> str:
    loc = [str(part) for part in error["loc"]]
    if error["type"] == "json_invalid":
        return "body"
    if len(loc) > 1 and loc[0] in _LOCATION_PREFIXES:
        loc = loc[1:]
    return ".".join(loc)


def _field_message(error: dict[str, Any]) -> str:
    error_type, ctx = error["type"], error.get("ctx", {})
    if error_type == "string_too_short":
        return "Wajib diisi" if ctx["min_length"] == 1 else f"Minimal {ctx['min_length']} karakter"
    if error_type == "string_too_long":
        return f"Maksimal {ctx['max_length']} karakter"
    if error_type == "enum":
        return f"Pilihan tidak valid, gunakan salah satu dari {ctx['expected']}"
    if error_type == "value_error":
        return str(ctx["error"])
    return _VALIDATION_MESSAGES.get(error_type, error["msg"])


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        status_code = next(
            (_STATUS_CODES[cls] for cls in type(exc).__mro__ if cls in _STATUS_CODES),
            400,
        )
        return JSONResponse(
            status_code=status_code,
            content=_error_content(exc.message, code=exc.code),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"field": _field_name(err), "message": _field_message(err)} for err in exc.errors()]
        return JSONResponse(
            status_code=422,
            content=_error_content("Data yang dikirim tidak valid", errors),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = _HTTP_MESSAGES.get(exc.status_code, str(exc.detail))
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_content(message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_error_content("Terjadi kesalahan pada server, silakan coba lagi"),
        )
