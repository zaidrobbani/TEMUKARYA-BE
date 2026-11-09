from datetime import UTC, datetime

from app.core.security import PasswordHasher
from app.core.unit_of_work import UnitOfWork
from app.modules.users.application.dto import CreateAdminInput, RegisterUserInput
from app.modules.users.domain.entities import SELF_REGISTRABLE_ROLES, User, UserRole
from app.modules.users.domain.exceptions import (
    EmailAlreadyRegisteredError,
    RoleNotRegistrableError,
    UserAccessDeniedError,
    UserNotFoundError,
)
from app.modules.users.domain.repositories import UserRepository


class _UserCreator:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, uow: UnitOfWork):
        self._users = users
        self._hasher = hasher
        self._uow = uow

    def _create(
        self,
        *,
        name: str,
        email: str,
        password: str,
        role: UserRole,
        phone_number: str | None = None,
        email_verified_at: datetime | None = None,
        terms_accepted_at: datetime | None = None,
    ) -> User:
        email = email.strip().lower()
        if self._users.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError(email)

        user = self._users.add(
            User(
                name=name.strip(),
                email=email,
                password_hash=self._hasher.hash(password),
                role=role,
                phone_number=phone_number,
                email_verified_at=email_verified_at,
                terms_accepted_at=terms_accepted_at,
            )
        )
        self._uow.commit()
        return user


class RegisterUser(_UserCreator):
    def execute(self, data: RegisterUserInput) -> User:
        if data.role not in SELF_REGISTRABLE_ROLES:
            raise RoleNotRegistrableError()

        return self._create(
            name=data.name,
            email=data.email,
            password=data.password,
            role=data.role,
            phone_number=data.phone_number,
            terms_accepted_at=datetime.now(UTC),
        )


class CreateAdmin(_UserCreator):
    def execute(self, data: CreateAdminInput) -> User:
        return self._create(
            name=data.name,
            email=data.email,
            password=data.password,
            role=UserRole.ADMIN,
            email_verified_at=datetime.now(UTC),
        )


class GetUser:
    def __init__(self, users: UserRepository):
        self._users = users

    def execute(self, user_id: str, requester: User) -> User:
        if requester.id != user_id and requester.role != UserRole.ADMIN:
            raise UserAccessDeniedError()

        user = self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user
