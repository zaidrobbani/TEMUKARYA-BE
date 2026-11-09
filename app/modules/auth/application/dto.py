from dataclasses import dataclass

from app.core.tokens import AccessToken
from app.modules.auth.domain.entities import LoginPortal
from app.modules.users.domain.entities import User


@dataclass(frozen=True)
class LoginInput:
    email: str
    password: str
    portal: LoginPortal = LoginPortal.MOBILE_APP


@dataclass(frozen=True)
class LoginResult:
    user: User
    access_token: AccessToken
