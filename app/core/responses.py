from datetime import UTC, datetime
from typing import Annotated, Generic, Literal, NotRequired, TypedDict, TypeVar

from pydantic import BaseModel, PlainSerializer

T = TypeVar("T")


def _serialize_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


UtcDateTime = Annotated[datetime, PlainSerializer(_serialize_utc, return_type=str)]


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str
    data: T | None = None


class FieldError(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    data: None = None
    errors: list[FieldError] | None = None
    code: str | None = None


class SuccessBody(TypedDict, Generic[T]):
    success: Literal[True]
    message: str
    data: T | None


class FieldErrorBody(TypedDict):
    field: str
    message: str


class ErrorBody(TypedDict):
    success: Literal[False]
    message: str
    data: None
    errors: NotRequired[list[FieldErrorBody]]
    code: NotRequired[str]


class OpenApiErrorResponse(TypedDict):
    model: type[ErrorResponse]


def success_response(message: str, data: T | None = None) -> SuccessBody[T]:
    return {"success": True, "message": message, "data": data}


def error_body(
    message: str,
    errors: list[FieldErrorBody] | None = None,
    code: str | None = None,
) -> ErrorBody:
    content: ErrorBody = {"success": False, "message": message, "data": None}
    if errors is not None:
        content["errors"] = errors
    if code is not None:
        content["code"] = code
    return content


def error_responses(*status_codes: int) -> dict[int | str, OpenApiErrorResponse]:
    return {code: {"model": ErrorResponse} for code in status_codes}
