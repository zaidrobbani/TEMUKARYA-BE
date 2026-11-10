from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NotificationCategory(StrEnum):
    PROJECT = "PROJECT"
    PAYMENT = "PAYMENT"
    MESSAGE = "MESSAGE"


class NotificationType(StrEnum):
    APPLICATION_RECEIVED = "APPLICATION_RECEIVED"
    APPLICATION_ACCEPTED = "APPLICATION_ACCEPTED"
    APPLICATION_NOT_SELECTED = "APPLICATION_NOT_SELECTED"
    AGREEMENT_UPDATED = "AGREEMENT_UPDATED"
    AGREEMENT_APPROVED = "AGREEMENT_APPROVED"
    AGREEMENT_CHANGES_REQUESTED = "AGREEMENT_CHANGES_REQUESTED"
    AGREEMENT_FINALIZED = "AGREEMENT_FINALIZED"
    PROJECT_CANCELLED = "PROJECT_CANCELLED"
    PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    WORK_STARTED = "WORK_STARTED"
    MILESTONE_COMPLETED = "MILESTONE_COMPLETED"
    SUBMISSION_RECEIVED = "SUBMISSION_RECEIVED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    SUBMISSION_APPROVED = "SUBMISSION_APPROVED"
    FUNDS_RELEASED = "FUNDS_RELEASED"
    REVIEW_RECEIVED = "REVIEW_RECEIVED"
    NEW_MESSAGE = "NEW_MESSAGE"


NOTIFICATION_TYPE_LABELS: dict[NotificationType, str] = {
    NotificationType.APPLICATION_RECEIVED: "Pengajuan baru",
    NotificationType.APPLICATION_ACCEPTED: "Pengajuan disetujui",
    NotificationType.APPLICATION_NOT_SELECTED: "Pengajuan tidak dipilih",
    NotificationType.AGREEMENT_UPDATED: "Kesepakatan diperbarui",
    NotificationType.AGREEMENT_APPROVED: "Kesepakatan disetujui satu pihak",
    NotificationType.AGREEMENT_CHANGES_REQUESTED: "Permintaan ubah rencana",
    NotificationType.AGREEMENT_FINALIZED: "Kesepakatan final",
    NotificationType.PROJECT_CANCELLED: "Project dibatalkan",
    NotificationType.PAYMENT_SUCCEEDED: "Pembayaran berhasil",
    NotificationType.PAYMENT_FAILED: "Pembayaran gagal",
    NotificationType.PAYMENT_RECEIVED: "Dana ditahan",
    NotificationType.WORK_STARTED: "Pengerjaan dimulai",
    NotificationType.MILESTONE_COMPLETED: "Milestone selesai",
    NotificationType.SUBMISSION_RECEIVED: "Hasil kerja dikirim",
    NotificationType.REVISION_REQUESTED: "Permintaan revisi",
    NotificationType.SUBMISSION_APPROVED: "Hasil disetujui",
    NotificationType.FUNDS_RELEASED: "Dana diteruskan",
    NotificationType.REVIEW_RECEIVED: "Ulasan baru",
    NotificationType.NEW_MESSAGE: "Pesan baru",
}

_PAYMENT_TYPES = {
    NotificationType.PAYMENT_SUCCEEDED,
    NotificationType.PAYMENT_FAILED,
    NotificationType.PAYMENT_RECEIVED,
    NotificationType.FUNDS_RELEASED,
}


def category_of(notification_type: str) -> NotificationCategory:
    if notification_type == NotificationType.NEW_MESSAGE:
        return NotificationCategory.MESSAGE
    if notification_type in _PAYMENT_TYPES:
        return NotificationCategory.PAYMENT
    return NotificationCategory.PROJECT


def types_of(category: NotificationCategory) -> tuple[str, ...]:
    return tuple(t.value for t in NotificationType if category_of(t) == category)


class ReferenceType(StrEnum):
    PROJECT = "PROJECT"
    CONVERSATION = "CONVERSATION"


@dataclass(frozen=True)
class Notification:
    id: str
    user_id: str
    notification_type: str
    title: str
    body: str
    reference_type: str | None
    reference_id: str | None
    created_at: datetime
    read_at: datetime | None = None

    @property
    def category(self) -> NotificationCategory:
        return category_of(self.notification_type)


@dataclass(frozen=True)
class NotificationPage:
    items: list[Notification]
    has_more: bool
    unread_count: int
    category_counts: dict[str, int]
