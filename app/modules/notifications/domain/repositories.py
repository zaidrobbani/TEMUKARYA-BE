from abc import ABC, abstractmethod
from datetime import datetime

from app.modules.notifications.domain.entities import Notification


class NotificationRepository(ABC):
    @abstractmethod
    def add(self, notification: Notification) -> None: ...

    @abstractmethod
    def list_for_user(
        self, user_id: str, types: tuple[str, ...] | None, unread_only: bool, limit: int, offset: int
    ) -> list[Notification]:
        """Urut terbaru dulu."""

    @abstractmethod
    def count_by_type(self, user_id: str) -> dict[str, int]: ...

    @abstractmethod
    def count_unread(self, user_id: str) -> int: ...

    @abstractmethod
    def get(self, user_id: str, notification_id: str) -> Notification | None: ...

    @abstractmethod
    def mark_read(self, user_id: str, notification_id: str, read_at: datetime) -> None:
        """Hanya mengisi read_at yang masih kosong."""

    @abstractmethod
    def mark_all_read(self, user_id: str, read_at: datetime) -> int: ...
