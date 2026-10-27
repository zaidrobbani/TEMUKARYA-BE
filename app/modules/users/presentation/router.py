from fastapi import APIRouter, Depends, status

from app.modules.users.application.dto import RegisterUserInput
from app.modules.users.application.use_cases import GetUser, RegisterUser
from app.modules.users.presentation.dependencies import get_user_use_case, register_user_use_case
from app.modules.users.presentation.schemas import RegisterUserRequest, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    body: RegisterUserRequest,
    use_case: RegisterUser = Depends(register_user_use_case),
):
    return use_case.execute(RegisterUserInput(**body.model_dump()))


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, use_case: GetUser = Depends(get_user_use_case)):
    return use_case.execute(user_id)
