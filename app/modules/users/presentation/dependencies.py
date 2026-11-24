import os
from pathlib import Path

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import API_PREFIX
from app.core.database import get_db
from app.core.dependencies import get_password_hasher, get_uow
from app.core.security import PasswordHasher
from app.core.unit_of_work import UnitOfWork
from app.modules.users.application.use_cases import (
    GetProfilePhoto,
    GetUser,
    RegisterUser,
    RemoveProfilePhoto,
    UpdateProfilePhoto,
)
from app.modules.users.domain.avatar import AvatarStorage
from app.modules.users.domain.repositories import UserRepository
from app.modules.users.infrastructure.avatar_storage import LocalAvatarStorage
from app.modules.users.infrastructure.repositories import SqlAlchemyUserRepository


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return SqlAlchemyUserRepository(db)


def register_user_use_case(
    users: UserRepository = Depends(get_user_repository),
    hasher: PasswordHasher = Depends(get_password_hasher),
    uow: UnitOfWork = Depends(get_uow),
) -> RegisterUser:
    return RegisterUser(users, hasher, uow)


def get_user_use_case(users: UserRepository = Depends(get_user_repository)) -> GetUser:
    return GetUser(users)


def get_avatar_storage() -> AvatarStorage:
    root = os.getenv("AVATAR_STORAGE_ROOT") or Path.cwd() / "storage" / "avatars"
    return LocalAvatarStorage(root)


def update_profile_photo_use_case(
    users: UserRepository = Depends(get_user_repository),
    storage: AvatarStorage = Depends(get_avatar_storage),
    uow: UnitOfWork = Depends(get_uow),
) -> UpdateProfilePhoto:
    return UpdateProfilePhoto(users, storage, uow, API_PREFIX)


def remove_profile_photo_use_case(
    users: UserRepository = Depends(get_user_repository),
    storage: AvatarStorage = Depends(get_avatar_storage),
    uow: UnitOfWork = Depends(get_uow),
) -> RemoveProfilePhoto:
    return RemoveProfilePhoto(users, storage, uow)


def get_profile_photo_use_case(
    users: UserRepository = Depends(get_user_repository),
    storage: AvatarStorage = Depends(get_avatar_storage),
) -> GetProfilePhoto:
    return GetProfilePhoto(users, storage)
