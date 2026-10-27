# Composition root modul users: satu-satunya tempat implementasi konkret dirakit ke use case.
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_password_hasher, get_uow
from app.core.security import PasswordHasher
from app.core.unit_of_work import UnitOfWork
from app.modules.users.application.use_cases import GetUser, RegisterUser
from app.modules.users.domain.repositories import UserRepository
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
