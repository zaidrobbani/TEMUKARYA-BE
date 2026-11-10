from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_uow
from app.core.unit_of_work import UnitOfWork
from app.modules.notifications.application.use_cases import (
    CountUnreadNotifications,
    ListNotifications,
    MarkAllNotificationsRead,
    MarkNotificationRead,
    Notifier,
)
from app.modules.notifications.domain.repositories import NotificationRepository
from app.modules.notifications.infrastructure.repositories import SqlAlchemyNotificationRepository


def get_notification_repository(db: Session = Depends(get_db)) -> NotificationRepository:
    return SqlAlchemyNotificationRepository(db)


def get_notifier(repository: NotificationRepository = Depends(get_notification_repository)) -> Notifier:
    return Notifier(repository)


def list_notifications_use_case(
    repository: NotificationRepository = Depends(get_notification_repository),
) -> ListNotifications:
    return ListNotifications(repository)


def count_unread_use_case(
    repository: NotificationRepository = Depends(get_notification_repository),
) -> CountUnreadNotifications:
    return CountUnreadNotifications(repository)


def mark_read_use_case(
    repository: NotificationRepository = Depends(get_notification_repository),
    uow: UnitOfWork = Depends(get_uow),
) -> MarkNotificationRead:
    return MarkNotificationRead(repository, uow)


def mark_all_read_use_case(
    repository: NotificationRepository = Depends(get_notification_repository),
    uow: UnitOfWork = Depends(get_uow),
) -> MarkAllNotificationsRead:
    return MarkAllNotificationsRead(repository, uow)
