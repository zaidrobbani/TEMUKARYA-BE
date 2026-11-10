from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.core.responses import UtcDateTime
from app.modules.payments.application.use_cases import PaymentDetail, PaymentHistoryPage, WalletEntriesPage
from app.modules.payments.domain.entities import (
    COMMISSION_PERCENT,
    DISPLAY_STATUS_LABELS,
    FUND_STATUS_LABELS,
    PAYMENT_METHOD_LABELS,
    PAYMENT_STATUS_LABELS,
    WALLET_ENTRY_LABELS,
    PaymentAttempt,
    PaymentOutcome,
    TransactionGroup,
    WalletBalance,
    WalletEntry,
)
from app.modules.workflow.domain.entities import status_label
from app.modules.workflow.presentation.schemas import UserSummaryResponse


def _label(labels: dict, value: str | None) -> str | None:
    if value is None:
        return None
    return next((label for key, label in labels.items() if key == value), value)


class SimulatePaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: PaymentOutcome = Field(
        PaymentOutcome.SUCCESS, description="Mekanisme demo: SUCCESS (default) atau FAILED"
    )


class PaymentProjectResponse(BaseModel):
    id: str
    title: str
    status: str
    status_label: str


class PaymentAgreementResponse(BaseModel):
    scope_of_work: str
    agreed_price: int
    agreed_deadline: date
    duration_days: int


class PaymentAttemptResponse(BaseModel):
    attempt_number: int
    status: str
    failure_reason: str | None
    attempted_at: UtcDateTime

    @classmethod
    def build(cls, attempt: PaymentAttempt) -> "PaymentAttemptResponse":
        return cls(
            attempt_number=attempt.attempt_number,
            status=attempt.status,
            failure_reason=attempt.failure_reason,
            attempted_at=attempt.attempted_at,
        )


class PaymentDetailResponse(BaseModel):
    id: str
    transaction_number: str | None = Field(description="Nomor bukti, terisi setelah pembayaran berhasil")
    status: str
    status_label: str
    fund_status: str | None
    fund_status_label: str | None
    display_status: str
    display_status_label: str
    payment_method: str
    payment_method_label: str
    is_simulation: bool = True
    gross_amount: int = Field(description="Nilai project disepakati")
    platform_fee_amount: int = Field(description="Biaya platform 5%")
    freelancer_amount: int = Field(description="Diterima freelancer (net)")
    total_amount: int = Field(description="Total dibayar UMKM = nilai project")
    commission_percent: int
    expires_at: UtcDateTime | None
    seconds_remaining: int | None = Field(description="Sisa waktu QRIS; 0 bila kedaluwarsa, null bila tidak berlaku")
    paid_at: UtcDateTime | None
    released_at: UtcDateTime | None
    created_at: UtcDateTime
    project: PaymentProjectResponse
    agreement: PaymentAgreementResponse
    umkm: UserSummaryResponse
    freelancer: UserSummaryResponse
    attempts: list[PaymentAttemptResponse]

    @classmethod
    def build(cls, detail: PaymentDetail) -> "PaymentDetailResponse":
        payment = detail.payment
        remaining = None
        if payment.expires_at is not None and payment.status == "MENUNGGU":
            remaining = max(0, int((payment.expires_at - detail.now).total_seconds()))
        return cls(
            id=payment.id,
            transaction_number=payment.transaction_number,
            status=payment.status,
            status_label=_label(PAYMENT_STATUS_LABELS, payment.status),
            fund_status=payment.fund_status,
            fund_status_label=_label(FUND_STATUS_LABELS, payment.fund_status),
            display_status=payment.display_status.value,
            display_status_label=DISPLAY_STATUS_LABELS[payment.display_status],
            payment_method=payment.payment_method,
            payment_method_label=_label(PAYMENT_METHOD_LABELS, payment.payment_method),
            gross_amount=payment.gross_amount,
            platform_fee_amount=payment.platform_fee_amount,
            freelancer_amount=payment.freelancer_amount,
            total_amount=payment.gross_amount,
            commission_percent=COMMISSION_PERCENT,
            expires_at=payment.expires_at if payment.status == "MENUNGGU" else None,
            seconds_remaining=remaining,
            paid_at=payment.paid_at,
            released_at=payment.released_at,
            created_at=payment.created_at,
            project=PaymentProjectResponse(
                id=detail.project.id,
                title=detail.project.title,
                status=detail.project.status,
                status_label=status_label(detail.project.status),
            ),
            agreement=PaymentAgreementResponse(
                scope_of_work=detail.agreement.scope_of_work,
                agreed_price=detail.agreement.agreed_price,
                agreed_deadline=detail.agreement.agreed_deadline,
                duration_days=detail.agreement.duration_days,
            ),
            umkm=UserSummaryResponse.build(detail.parties.umkm),
            freelancer=UserSummaryResponse.build(detail.parties.freelancer),
            attempts=[PaymentAttemptResponse.build(a) for a in detail.attempts],
        )


class PaymentHistoryItemResponse(BaseModel):
    payment_id: str
    transaction_number: str | None
    project_id: str
    project_title: str
    freelancer_id: str
    freelancer_name: str
    amount: int
    status: str
    fund_status: str | None
    display_status: str
    display_status_label: str
    paid_at: UtcDateTime | None
    created_at: UtcDateTime
    occurred_at: UtcDateTime = Field(description="paid_at bila sudah dibayar, selain itu created_at; dipakai untuk grup bulan")


class PaymentHistoryCounts(BaseModel):
    ALL: int
    PENDING: int
    HELD: int
    COMPLETED: int
    CANCELLED: int


class PaymentHistoryResponse(BaseModel):
    items: list[PaymentHistoryItemResponse]
    limit: int
    offset: int
    has_more: bool
    counts: PaymentHistoryCounts

    @classmethod
    def build(cls, page: PaymentHistoryPage, limit: int, offset: int) -> "PaymentHistoryResponse":
        items = []
        for row in page.items:
            p = row.payment
            items.append(
                PaymentHistoryItemResponse(
                    payment_id=p.id,
                    transaction_number=p.transaction_number,
                    project_id=row.project_id,
                    project_title=row.project_title,
                    freelancer_id=row.freelancer_id,
                    freelancer_name=row.freelancer_name,
                    amount=p.gross_amount,
                    status=p.status,
                    fund_status=p.fund_status,
                    display_status=p.display_status.value,
                    display_status_label=DISPLAY_STATUS_LABELS[p.display_status],
                    paid_at=p.paid_at,
                    created_at=p.created_at,
                    occurred_at=p.paid_at or p.created_at,
                )
            )
        counts = {g.value: page.counts.get(g.value, 0) for g in TransactionGroup}
        return cls(items=items, limit=limit, offset=offset, has_more=page.has_more, counts=counts)


class WalletResponse(BaseModel):
    available_balance: int = Field(description="Saldo tersedia")
    held_balance: int = Field(description="Saldo tertahan dari project berjalan")
    total_balance: int

    @classmethod
    def build(cls, balance: WalletBalance) -> "WalletResponse":
        return cls(available_balance=balance.available, held_balance=balance.held, total_balance=balance.total)


class WalletEntryResponse(BaseModel):
    id: str
    type: str
    type_label: str
    direction: str = Field(description="IN untuk dana masuk")
    amount: int
    payment_id: str
    project_id: str
    project_title: str
    still_held: bool = Field(description="True bila dana dari project ini masih ditahan")
    created_at: UtcDateTime

    @classmethod
    def build(cls, entry: WalletEntry) -> "WalletEntryResponse":
        return cls(
            id=entry.id,
            type=entry.entry_type.value,
            type_label=WALLET_ENTRY_LABELS[entry.entry_type],
            direction="IN",
            amount=entry.amount,
            payment_id=entry.payment_id,
            project_id=entry.project_id,
            project_title=entry.project_title,
            still_held=entry.still_held,
            created_at=entry.created_at,
        )


class WalletEntriesResponse(BaseModel):
    items: list[WalletEntryResponse]
    limit: int
    offset: int
    has_more: bool

    @classmethod
    def build(cls, page: WalletEntriesPage, limit: int, offset: int) -> "WalletEntriesResponse":
        return cls(
            items=[WalletEntryResponse.build(e) for e in page.items], limit=limit, offset=offset, has_more=page.has_more
        )
