from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.domain.entities import User, UserRole
from app.modules.users.domain.repositories import UserRepository
from app.modules.users.infrastructure.models import UserModel


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, user_id: str) -> User | None:
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
            phone_number=user.phone_number,
            profile_image_url=user.profile_image_url,
        )
        self._session.add(model)
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
        phone_number=model.phone_number,
        profile_image_url=model.profile_image_url,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
