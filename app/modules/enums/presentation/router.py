from fastapi import APIRouter

from app.core.responses import ApiResponse, error_responses, success_response
from app.modules.enums.exceptions import EnumNotFoundError
from app.modules.enums.presentation.schemas import EnumOptionResponse
from app.modules.enums.registry import ENUMS

router = APIRouter(prefix="/enums", tags=["enums"])


@router.get("", response_model=ApiResponse[dict[str, list[EnumOptionResponse]]])
def list_enums():
    return success_response("Daftar enum berhasil diambil", ENUMS)


@router.get(
    "/{name}",
    response_model=ApiResponse[list[EnumOptionResponse]],
    responses=error_responses(404),
)
def get_enum(name: str):
    if name not in ENUMS:
        raise EnumNotFoundError(name)
    return success_response(f"Enum {name} berhasil diambil", ENUMS[name])
