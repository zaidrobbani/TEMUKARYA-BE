from datetime import UTC, datetime
from typing import BinaryIO

from app.core.security import PasswordHasher
from app.core.unit_of_work import UnitOfWork
from app.modules.users.application.dto import CreateAdminInput, CreateVerifiedUserInput, RegisterUserInput
from app.modules.users.domain.entities import SELF_REGISTRABLE_ROLES, User, UserRole
from app.modules.users.domain.exceptions import (
    EmailAlreadyRegisteredError,
    RoleNotRegistrableError,
    UserAccessDeniedError,
    UserNotFoundError,
)
from app.modules.users.domain.avatar import AvatarNotFoundError, AvatarStorage, avatar_key_from_url, avatar_url
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


class CreateVerifiedUser(_UserCreator):
    def execute(self, data: CreateVerifiedUserInput) -> User:
        now = datetime.now(UTC)
        return self._create(
            name=data.name,
            email=data.email,
            password=data.password,
            role=data.role,
            phone_number=data.phone_number,
            email_verified_at=now,
            terms_accepted_at=None if data.role == UserRole.ADMIN else now,
        )


class CreateAdmin(CreateVerifiedUser):
    def execute(self, data: CreateAdminInput) -> User:
        return super().execute(
            CreateVerifiedUserInput(name=data.name, email=data.email, password=data.password, role=UserRole.ADMIN)
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


class UpdateProfilePhoto:
    def __init__(self, users: UserRepository, storage: AvatarStorage, uow: UnitOfWork, api_prefix: str):
        self._users = users
        self._storage = storage
        self._uow = uow
        self._api_prefix = api_prefix

    def execute(self, user: User, source: BinaryIO) -> User:
        old_key = avatar_key_from_url(user.profile_image_url)
        key = self._storage.save(source)
        try:
            self._users.update_profile_image(user.id, avatar_url(self._api_prefix, user.id, key), datetime.now(UTC))
            self._uow.commit()
        except Exception:
            self._storage.delete(key)
            raise
        if old_key:
            self._storage.delete(old_key)
        updated = self._users.get_by_id(user.id)
        if updated is None:
            raise UserNotFoundError(user.id)
        return updated


class RemoveProfilePhoto:
    def __init__(self, users: UserRepository, storage: AvatarStorage, uow: UnitOfWork):
        self._users = users
        self._storage = storage
        self._uow = uow

    def execute(self, user: User) -> User:
        old_key = avatar_key_from_url(user.profile_image_url)
        self._users.update_profile_image(user.id, None, datetime.now(UTC))
        self._uow.commit()
        if old_key:
            self._storage.delete(old_key)
        updated = self._users.get_by_id(user.id)
        if updated is None:
            raise UserNotFoundError(user.id)
        return updated


class GetProfilePhoto:
    def __init__(self, users: UserRepository, storage: AvatarStorage):
        self._users = users
        self._storage = storage

    def execute(self, user_id: str) -> BinaryIO:
        user = self._users.get_by_id(user_id)
        key = avatar_key_from_url(user.profile_image_url) if user else None
        if key is None:
            raise AvatarNotFoundError()
        return self._storage.open(key)
