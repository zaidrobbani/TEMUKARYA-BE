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
    RegisterDeviceToken,
    UnregisterDeviceToken,
)
from app.modules.notifications.domain.repositories import DeviceTokenRepository, NotificationRepository
from app.modules.notifications.infrastructure.device_tokens import SqlAlchemyDeviceTokenRepository
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


def get_device_token_repository(db: Session = Depends(get_db)) -> DeviceTokenRepository:
    return SqlAlchemyDeviceTokenRepository(db)


def register_device_use_case(
    repository: DeviceTokenRepository = Depends(get_device_token_repository),
    uow: UnitOfWork = Depends(get_uow),
) -> RegisterDeviceToken:
    return RegisterDeviceToken(repository, uow)


def unregister_device_use_case(
    repository: DeviceTokenRepository = Depends(get_device_token_repository),
    uow: UnitOfWork = Depends(get_uow),
) -> UnregisterDeviceToken:
    return UnregisterDeviceToken(repository, uow)



# ------------------------------------------------------------
# WebSocket notifikasi: autentikasi token & hitung belum dibaca dengan session per aksi
# (bukan per koneksi) agar koneksi pool tidak tertahan selama socket terbuka.
# ------------------------------------------------------------

def _authenticate_socket(token: str) -> str:
    from app.core.database import SessionLocal
    from app.core.dependencies import get_token_service
    from app.modules.auth.application.use_cases import AuthenticateToken
    from app.modules.auth.infrastructure.repositories import SqlAlchemyRevokedTokenRepository
    from app.modules.users.infrastructure.repositories import SqlAlchemyUserRepository

    session = SessionLocal()
    try:
        return AuthenticateToken(
            SqlAlchemyUserRepository(session),
            SqlAlchemyRevokedTokenRepository(session),
            get_token_service(),
        ).execute(token).user.id
    finally:
        session.close()


def _count_unread(user_id: str) -> int:
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        return CountUnreadNotifications(SqlAlchemyNotificationRepository(session)).execute(user_id)
    finally:
        session.close()


def get_notification_socket_authenticator():
    return _authenticate_socket


def get_unread_counter():
    return _count_unread


def get_notification_hub():
    from app.modules.notifications.infrastructure.realtime import notification_hub

    return notification_hub
