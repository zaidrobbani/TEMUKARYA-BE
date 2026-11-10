from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.database import from_db_utc, to_db_utc
from app.modules.notifications.domain.entities import Notification
from app.modules.notifications.domain.repositories import NotificationRepository
from app.modules.notifications.infrastructure.models import NotificationModel


def _to_entity(model: NotificationModel) -> Notification:
    return Notification(
        id=model.id,
        user_id=model.user_id,
        notification_type=model.notification_type,
        title=model.title,
        body=model.body,
        reference_type=model.reference_type,
        reference_id=model.reference_id,
        created_at=from_db_utc(model.created_at),
        read_at=from_db_utc(model.read_at),
    )


class SqlAlchemyNotificationRepository(NotificationRepository):
    def __init__(self, session: Session):
        self._session = session

    def add(self, notification: Notification) -> None:
        self._session.add(
            NotificationModel(
                id=notification.id,
                user_id=notification.user_id,
                notification_type=notification.notification_type,
                title=notification.title,
                body=notification.body,
                reference_type=notification.reference_type,
                reference_id=notification.reference_id,
                created_at=to_db_utc(notification.created_at),
            )
        )
        self._session.flush()

    def list_for_user(
        self, user_id: str, types: tuple[str, ...] | None, unread_only: bool, limit: int, offset: int
    ) -> list[Notification]:
        query = select(NotificationModel).where(NotificationModel.user_id == user_id)
        if types is not None:
            query = query.where(NotificationModel.notification_type.in_(types))
        if unread_only:
            query = query.where(NotificationModel.read_at.is_(None))
        query = query.order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc())
        return [_to_entity(m) for m in self._session.scalars(query.limit(limit).offset(offset))]

    def count_by_type(self, user_id: str) -> dict[str, int]:
        rows = self._session.execute(
            select(NotificationModel.notification_type, func.count())
            .where(NotificationModel.user_id == user_id)
            .group_by(NotificationModel.notification_type)
        )
        return {row[0]: int(row[1]) for row in rows}

    def count_unread(self, user_id: str) -> int:
        return int(
            self._session.scalar(
                select(func.count()).where(
                    NotificationModel.user_id == user_id, NotificationModel.read_at.is_(None)
                )
            )
        )

    def get(self, user_id: str, notification_id: str) -> Notification | None:
        model = self._session.scalar(
            select(NotificationModel).where(
                NotificationModel.id == notification_id, NotificationModel.user_id == user_id
            )
        )
        return _to_entity(model) if model else None

    def mark_read(self, user_id: str, notification_id: str, read_at: datetime) -> None:
        self._session.execute(
            update(NotificationModel)
            .where(
                NotificationModel.id == notification_id,
                NotificationModel.user_id == user_id,
                NotificationModel.read_at.is_(None),
            )
            .values(read_at=to_db_utc(read_at))
            .execution_options(synchronize_session=False)
        )
        self._session.expire_all()

    def mark_all_read(self, user_id: str, read_at: datetime) -> int:
        result = self._session.execute(
            update(NotificationModel)
            .where(NotificationModel.user_id == user_id, NotificationModel.read_at.is_(None))
            .values(read_at=to_db_utc(read_at))
            .execution_options(synchronize_session=False)
        )
        self._session.expire_all()
        return int(result.rowcount)
