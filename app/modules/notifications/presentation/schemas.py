from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.responses import UtcDateTime
from app.modules.notifications.domain.entities import Notification


class NotificationResponse(BaseModel):
    id: str
    type: str
    category: str
    title: str
    body: str
    reference_type: str | None
    reference_id: str | None
    is_read: bool
    created_at: UtcDateTime
    read_at: UtcDateTime | None

    @classmethod
    def from_entity(cls, n: Notification) -> "NotificationResponse":
        return cls(
            id=n.id,
            type=n.notification_type,
            category=n.category.value,
            title=n.title,
            body=n.body,
            reference_type=n.reference_type,
            reference_id=n.reference_id,
            is_read=n.read_at is not None,
            created_at=n.created_at,
            read_at=n.read_at,
        )


class NotificationCounts(BaseModel):
    ALL: int
    PROJECT: int
    PAYMENT: int
    MESSAGE: int


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    limit: int
    offset: int
    has_more: bool
    unread_count: int
    counts: NotificationCounts


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkAllReadResponse(BaseModel):
    updated: int


class DeviceTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=512, pattern=r"^\S+$")
    platform: Literal["ANDROID"] = "ANDROID"


class DeviceTokenDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=512)
    # Android mengirim body yang sama dengan pendaftaran; platform diterima tapi tidak dipakai.
    platform: Literal["ANDROID"] | None = None
