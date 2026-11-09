from datetime import UTC, datetime

from sqlalchemy import exists, func, insert, select, update
from sqlalchemy.orm import Session

from app.core.database import from_db_utc, to_db_utc
from app.modules.auth.domain.entities import AuthActionPurpose, AuthActionToken
from app.modules.auth.domain.repositories import AuthActionTokenRepository, RevokedTokenRepository
from app.modules.auth.infrastructure.models import AuthActionTokenModel, RevokedTokenModel


class SqlAlchemyRevokedTokenRepository(RevokedTokenRepository):
    def __init__(self, session: Session):
        self._session = session

    def add(self, jti: str, user_id: str, expires_at: datetime) -> None:
        self._session.execute(
            insert(RevokedTokenModel)
            .prefix_with("IGNORE")
            .values(
                jti=jti,
                user_id=user_id,
                expires_at=expires_at.astimezone(UTC).replace(tzinfo=None),
            )
        )

    def exists(self, jti: str) -> bool:
        return bool(self._session.scalar(select(exists().where(RevokedTokenModel.jti == jti))))


class SqlAlchemyAuthActionTokenRepository(AuthActionTokenRepository):
    def __init__(self, session: Session):
        self._session = session

    def add(self, token: AuthActionToken) -> None:
        self._session.add(
            AuthActionTokenModel(
                user_id=token.user_id,
                purpose=token.purpose.value,
                token_hash=token.token_hash,
                expires_at=to_db_utc(token.expires_at),
                created_at=to_db_utc(token.created_at),
            )
        )
        self._session.flush()

    def get_by_hash(self, token_hash: str, purpose: AuthActionPurpose) -> AuthActionToken | None:
        model = self._session.scalar(
            select(AuthActionTokenModel).where(
                AuthActionTokenModel.token_hash == token_hash,
                AuthActionTokenModel.purpose == purpose.value,
            )
        )
        return _to_entity(model) if model else None

    def latest_created_at(self, user_id: str, purpose: AuthActionPurpose) -> datetime | None:
        latest = self._session.scalar(
            select(func.max(AuthActionTokenModel.created_at)).where(
                AuthActionTokenModel.user_id == user_id,
                AuthActionTokenModel.purpose == purpose.value,
            )
        )
        return from_db_utc(latest)

    def invalidate_active(self, user_id: str, purpose: AuthActionPurpose, at: datetime) -> None:
        self._session.execute(
            update(AuthActionTokenModel)
            .where(
                AuthActionTokenModel.user_id == user_id,
                AuthActionTokenModel.purpose == purpose.value,
                AuthActionTokenModel.used_at.is_(None),
            )
            .values(used_at=to_db_utc(at))
        )

    def consume(self, token_id: str, at: datetime) -> bool:
        result = self._session.execute(
            update(AuthActionTokenModel)
            .where(AuthActionTokenModel.id == token_id, AuthActionTokenModel.used_at.is_(None))
            .values(used_at=to_db_utc(at))
        )
        return result.rowcount == 1


def _to_entity(model: AuthActionTokenModel) -> AuthActionToken:
    return AuthActionToken(
        id=model.id,
        user_id=model.user_id,
        purpose=AuthActionPurpose(model.purpose),
        token_hash=model.token_hash,
        expires_at=from_db_utc(model.expires_at),
        created_at=from_db_utc(model.created_at),
        used_at=from_db_utc(model.used_at),
    )
