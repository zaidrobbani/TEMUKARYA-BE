from dataclasses import dataclass

from fastapi import Depends

from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.users.domain.entities import User, UserRole


@dataclass(frozen=True)
class AuthenticatedProfileUser:
    user_id: str
    role: UserRole


def get_authenticated_profile_user(user: User = Depends(get_current_user)) -> AuthenticatedProfileUser:
    return AuthenticatedProfileUser(user_id=user.id, role=user.role)
