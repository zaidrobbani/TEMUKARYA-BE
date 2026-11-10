from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.unit_of_work import UnitOfWork
from app.modules.notifications.domain.entities import (
    Notification,
    NotificationCategory,
    NotificationPage,
    NotificationType,
    types_of,
)
from app.modules.notifications.domain.repositories import NotificationRepository

Clock = Callable[[], datetime]
MAX_LIMIT = 100
_TITLE_MAX = 180
_BODY_MAX = 1000


def utc_now() -> datetime:
    return datetime.now(UTC)


def _clip(value: str, size: int) -> str:
    value = " ".join(value.split())
    return value if len(value) <= size else value[: size - 1] + "…"


class Notifier:
    """Kontrak notify() untuk semua modul. Tidak commit: ikut transaksi pemanggil."""

    def __init__(self, repository: NotificationRepository, clock: Clock = utc_now):
        self._repository = repository
        self._clock = clock

    def notify(
        self,
        user_id: str,
        type: NotificationType,
        title: str,
        body: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
    ) -> Notification:
        notification = Notification(
            id=str(uuid4()),
            user_id=user_id,
            notification_type=NotificationType(type).value,
            title=_clip(title, _TITLE_MAX),
            body=_clip(body, _BODY_MAX),
            reference_type=reference_type,
            reference_id=reference_id,
            created_at=self._clock(),
        )
        self._repository.add(notification)
        return notification


def _validate_page(limit: int, offset: int) -> None:
    if not 1 <= limit <= MAX_LIMIT:
        raise BadRequestError(f"Limit harus 1 sampai {MAX_LIMIT}")
    if offset < 0:
        raise BadRequestError("Offset tidak boleh negatif")


class ListNotifications:
    def __init__(self, repository: NotificationRepository):
        self._repository = repository

    def execute(
        self,
        user_id: str,
        category: NotificationCategory | None = None,
        unread_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> NotificationPage:
        _validate_page(limit, offset)
        types = types_of(category) if category else None
        rows = self._repository.list_for_user(user_id, types, unread_only, limit + 1, offset)
        by_type = self._repository.count_by_type(user_id)
        counts = {c.value: sum(by_type.get(t, 0) for t in types_of(c)) for c in NotificationCategory}
        counts["ALL"] = sum(by_type.values())
        return NotificationPage(
            items=rows[:limit],
            has_more=len(rows) > limit,
            unread_count=self._repository.count_unread(user_id),
            category_counts=counts,
        )


class CountUnreadNotifications:
    def __init__(self, repository: NotificationRepository):
        self._repository = repository

    def execute(self, user_id: str) -> int:
        return self._repository.count_unread(user_id)


class MarkNotificationRead:
    def __init__(self, repository: NotificationRepository, uow: UnitOfWork, clock: Clock = utc_now):
        self._repository = repository
        self._uow = uow
        self._clock = clock

    def execute(self, user_id: str, notification_id: str) -> Notification:
        if self._repository.get(user_id, notification_id) is None:
            raise NotFoundError("Notifikasi tidak ditemukan")
        self._repository.mark_read(user_id, notification_id, self._clock())
        self._uow.commit()
        return self._repository.get(user_id, notification_id)


class MarkAllNotificationsRead:
    def __init__(self, repository: NotificationRepository, uow: UnitOfWork, clock: Clock = utc_now):
        self._repository = repository
        self._uow = uow
        self._clock = clock

    def execute(self, user_id: str) -> int:
        updated = self._repository.mark_all_read(user_id, self._clock())
        self._uow.commit()
        return updated
