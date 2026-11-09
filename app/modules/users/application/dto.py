from dataclasses import dataclass

from app.modules.users.domain.entities import UserRole


@dataclass(frozen=True)
class RegisterUserInput:
    name: str
    email: str
    password: str
    role: UserRole
    phone_number: str | None = None


@dataclass(frozen=True)
class CreateAdminInput:
    name: str
    email: str
    password: str
