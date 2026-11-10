from dataclasses import dataclass

from app.modules.applications.domain.entities import APPLICATION_STATUS_LABELS
from app.modules.notifications.domain.entities import NOTIFICATION_TYPE_LABELS, NotificationCategory
from app.modules.payments.domain.entities import (
    DISPLAY_STATUS_LABELS,
    FUND_STATUS_LABELS,
    PAYMENT_STATUS_LABELS,
    WALLET_ENTRY_LABELS,
    PaymentOutcome,
    TransactionGroup,
)
from app.modules.reviews.domain.entities import REVIEW_HIGHLIGHT_LABELS
from app.modules.submissions.domain.entities import REVIEW_DECISION_LABELS
from app.modules.users.domain.entities import SELF_REGISTRABLE_ROLES, UserRole
from app.modules.workflow.domain.entities import (
    AGREEMENT_STATUS_LABELS,
    CANCEL_REASON_LABELS,
    PROJECT_STATUS_LABELS,
    WORKFLOW_ACTION_LABELS,
)


@dataclass(frozen=True)
class EnumOption:
    value: str
    label: str


def _options(labels: dict) -> list[EnumOption]:
    return [EnumOption(str(value), label) for value, label in labels.items()]


_USER_ROLE_LABELS: dict[UserRole, str] = {
    UserRole.UMKM: "Pemilik UMKM",
    UserRole.FREELANCER: "Freelancer Digital",
    UserRole.ADMIN: "Admin",
}

ENUMS: dict[str, list[EnumOption]] = {
    "user_roles": [EnumOption(role.value, label) for role, label in _USER_ROLE_LABELS.items()],
    "registration_roles": [
        EnumOption(role.value, label)
        for role, label in _USER_ROLE_LABELS.items()
        if role in SELF_REGISTRABLE_ROLES
    ],
    "project_statuses": _options(PROJECT_STATUS_LABELS),
    "application_statuses": _options(APPLICATION_STATUS_LABELS),
    "agreement_statuses": _options(AGREEMENT_STATUS_LABELS),
    "cancel_reasons": _options(CANCEL_REASON_LABELS),
    "workflow_actions": _options(WORKFLOW_ACTION_LABELS),
    "payment_statuses": _options(PAYMENT_STATUS_LABELS),
    "fund_statuses": _options(FUND_STATUS_LABELS),
    "payment_display_statuses": _options(DISPLAY_STATUS_LABELS),
    "payment_outcomes": [
        EnumOption(PaymentOutcome.SUCCESS.value, "Berhasil"),
        EnumOption(PaymentOutcome.FAILED.value, "Gagal"),
    ],
    "transaction_groups": [
        EnumOption(TransactionGroup.ALL.value, "Semua"),
        EnumOption(TransactionGroup.PENDING.value, "Menunggu"),
        EnumOption(TransactionGroup.HELD.value, "Dana Ditahan"),
        EnumOption(TransactionGroup.COMPLETED.value, "Selesai"),
        EnumOption(TransactionGroup.CANCELLED.value, "Dibatalkan"),
    ],
    "wallet_entry_types": _options(WALLET_ENTRY_LABELS),
    "submission_review_decisions": _options(REVIEW_DECISION_LABELS),
    "review_highlights": _options(REVIEW_HIGHLIGHT_LABELS),
    "notification_categories": [
        EnumOption(NotificationCategory.PROJECT.value, "Project"),
        EnumOption(NotificationCategory.PAYMENT.value, "Pembayaran"),
        EnumOption(NotificationCategory.MESSAGE.value, "Pesan"),
    ],
    "notification_types": _options(NOTIFICATION_TYPE_LABELS),
}
