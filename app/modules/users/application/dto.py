from dataclasses import dataclass

from app.modules.users.domain.entities import UserRole


@dataclass(frozen=True)
class RegisterUserInput:
    name: str
    email: str
    password: str
    role: UserRole
