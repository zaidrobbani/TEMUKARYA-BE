from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import from_db_utc, to_db_utc
from app.modules.users.domain.entities import User, UserRole
from app.modules.users.domain.exceptions import EmailAlreadyRegisteredError
from app.modules.users.domain.repositories import UserRepository
from app.modules.users.infrastructure.models import UserModel

_MYSQL_DUPLICATE_ENTRY = 1062


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
            email_verified_at=to_db_utc(user.email_verified_at) if user.email_verified_at else None,
            terms_accepted_at=to_db_utc(user.terms_accepted_at) if user.terms_accepted_at else None,
        )
        self._session.add(model)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            if exc.orig.args[0] == _MYSQL_DUPLICATE_ENTRY:
                raise EmailAlreadyRegisteredError(user.email) from exc
            raise
        self._session.refresh(model)
        return _to_entity(model)

    def mark_email_verified(self, user_id: str, verified_at: datetime) -> None:
        self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(email_verified_at=to_db_utc(verified_at))
        )

    def update_password(self, user_id: str, password_hash: str, changed_at: datetime) -> None:
        self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(password_hash=password_hash, password_changed_at=to_db_utc(changed_at))
        )


def _to_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        name=model.name,
        email=model.email,
        password_hash=model.password_hash,
        role=UserRole(model.role),
        phone_number=model.phone_number,
        profile_image_url=model.profile_image_url,
        email_verified_at=from_db_utc(model.email_verified_at),
        password_changed_at=from_db_utc(model.password_changed_at),
        terms_accepted_at=from_db_utc(model.terms_accepted_at),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
