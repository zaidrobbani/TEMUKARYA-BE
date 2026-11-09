from fastapi import APIRouter, Depends

from app.core.responses import ApiResponse, error_responses, success_response
from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.users.application.use_cases import GetUser
from app.modules.users.domain.entities import User
from app.modules.users.presentation.dependencies import get_user_use_case
from app.modules.users.presentation.schemas import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/{user_id}",
    response_model=ApiResponse[UserResponse],
    responses=error_responses(401, 403, 404),
)
def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    use_case: GetUser = Depends(get_user_use_case),
):
    user = use_case.execute(user_id, requester=current_user)
    return success_response("Data user berhasil diambil", user)
