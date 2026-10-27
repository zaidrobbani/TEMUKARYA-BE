from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.domain.entities import User, UserRole
from app.modules.users.domain.repositories import UserRepository
from app.modules.users.infrastructure.models import UserModel


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, user_id: int) -> User | None:
        model = self._session.get(UserModel, user_id)
        return _to_entity(model) if model else None

    def get_by_email(self, email: str) -> User | None:
        model = self._session.scalar(select(UserModel).where(UserModel.email == email))
        return _to_entity(model) if model else None

    def add(self, user: User) -> User:
        model = UserModel(
            name=user.name,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role.value,
        )
        self._session.add(model)
        # flush + refresh supaya id & created_at dari database terisi sebelum commit
        self._session.flush()
        self._session.refresh(model)
        return _to_entity(model)


def _to_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        name=model.name,
        email=model.email,
        password_hash=model.password_hash,
        role=UserRole(model.role),
        created_at=model.created_at,
    )
