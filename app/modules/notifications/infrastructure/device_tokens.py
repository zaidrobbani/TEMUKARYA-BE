from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.notifications.domain.repositories import DeviceTokenRepository
from app.modules.notifications.infrastructure.models import DeviceTokenModel


class SqlAlchemyDeviceTokenRepository(DeviceTokenRepository):
    def __init__(self, session: Session):
        self._session = session

    def upsert(self, user_id: str, token: str, platform: str) -> None:
        row = self._session.scalar(select(DeviceTokenModel).where(DeviceTokenModel.token == token).with_for_update())
        if row is None:
            self._session.add(DeviceTokenModel(user_id=user_id, token=token, platform=platform))
        else:
            row.user_id = user_id
            row.platform = platform
        self._session.flush()

    def remove(self, user_id: str, token: str) -> None:
        self._session.execute(
            delete(DeviceTokenModel).where(DeviceTokenModel.user_id == user_id, DeviceTokenModel.token == token)
        )

    def tokens_for(self, user_id: str) -> list[str]:
        return list(self._session.scalars(select(DeviceTokenModel.token).where(DeviceTokenModel.user_id == user_id)))

    def remove_tokens(self, tokens: list[str]) -> None:
        if tokens:
            self._session.execute(delete(DeviceTokenModel).where(DeviceTokenModel.token.in_(tokens)))
