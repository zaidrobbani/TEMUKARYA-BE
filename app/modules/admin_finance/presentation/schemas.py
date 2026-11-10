from datetime import date

from pydantic import BaseModel

from app.core.responses import UtcDateTime
from app.modules.admin_finance.application.use_cases import CommissionPage, IncomeChart, TransactionPage
from app.modules.admin_finance.domain.entities import AdminTransaction, AdminTransactionDetail, FinanceSummary
from app.modules.payments.domain.entities import (
    COMMISSION_PERCENT,
    DISPLAY_STATUS_LABELS,
    FUND_STATUS_LABELS,
    PAYMENT_STATUS_LABELS,
)
from app.modules.payments.presentation.schemas import PaymentAttemptResponse
from app.modules.workflow.domain.entities import status_label


def _label(labels: dict, value: str | None) -> str | None:
    if value is None:
        return None
    return next((label for key, label in labels.items() if key == value), value)


class FinanceSummaryResponse(BaseModel):
    total_income: int
    income_this_month: int
    commission_percent: int
    total_paid_amount: int
    held_amount: int
    released_amount: int
    successful_transactions: int
    pending_transactions: int
    failed_transactions: int
    cancelled_transactions: int
    total_transactions: int

    @classmethod
    def build(cls, summary: FinanceSummary) -> "FinanceSummaryResponse":
        return cls(commission_percent=COMMISSION_PERCENT, **summary.__dict__)


class AdminTransactionResponse(BaseModel):
    payment_id: str
    transaction_number: str | None
    project_id: str
    project_title: str
    project_status: str
    project_status_label: str
    umkm_id: str
    umkm_name: str
    umkm_business_name: str | None
    freelancer_id: str
    freelancer_name: str
    gross_amount: int
    platform_fee_amount: int
    freelancer_amount: int
    payment_method: str
    status: str
    status_label: str
    fund_status: str | None
    fund_status_label: str | None
    display_status: str
    display_status_label: str
    created_at: UtcDateTime
    paid_at: UtcDateTime | None
    released_at: UtcDateTime | None

    @classmethod
    def build(cls, row: AdminTransaction) -> "AdminTransactionResponse":
        p = row.payment
        return cls(
            payment_id=p.id,
            transaction_number=p.transaction_number,
            project_id=row.project_id,
            project_title=row.project_title,
            project_status=row.project_status,
            project_status_label=status_label(row.project_status),
            umkm_id=row.umkm_id,
            umkm_name=row.umkm_name,
            umkm_business_name=row.umkm_business_name,
            freelancer_id=row.freelancer_id,
            freelancer_name=row.freelancer_name,
            gross_amount=p.gross_amount,
            platform_fee_amount=p.platform_fee_amount,
            freelancer_amount=p.freelancer_amount,
            payment_method=p.payment_method,
            status=p.status,
            status_label=_label(PAYMENT_STATUS_LABELS, p.status),
            fund_status=p.fund_status,
            fund_status_label=_label(FUND_STATUS_LABELS, p.fund_status),
            display_status=p.display_status.value,
            display_status_label=DISPLAY_STATUS_LABELS[p.display_status],
            created_at=p.created_at,
            paid_at=p.paid_at,
            released_at=p.released_at,
        )


class AdminTransactionDetailResponse(AdminTransactionResponse):
    attempts: list[PaymentAttemptResponse]

    @classmethod
    def from_detail(cls, detail: AdminTransactionDetail) -> "AdminTransactionDetailResponse":
        base = AdminTransactionResponse.build(detail.transaction)
        return cls(
            **base.__dict__,
            attempts=[PaymentAttemptResponse.build(a) for a in detail.attempts],
        )


class TransactionListResponse(BaseModel):
    items: list[AdminTransactionResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

    @classmethod
    def build(cls, page: TransactionPage, limit: int, offset: int) -> "TransactionListResponse":
        return cls(
            items=[AdminTransactionResponse.build(r) for r in page.items],
            total=page.total,
            limit=limit,
            offset=offset,
            has_more=page.has_more,
        )


class CommissionListResponse(TransactionListResponse):
    commission_percent: int
    total_commission: int
    total_gross_amount: int

    @classmethod
    def from_page(cls, page: CommissionPage, limit: int, offset: int) -> "CommissionListResponse":
        return cls(
            items=[AdminTransactionResponse.build(r) for r in page.items],
            total=page.total,
            limit=limit,
            offset=offset,
            has_more=page.has_more,
            commission_percent=COMMISSION_PERCENT,
            total_commission=page.total_commission,
            total_gross_amount=page.total_gross_amount,
        )


class IncomePointResponse(BaseModel):
    period_start: date
    label: str
    income: int
    gross_amount: int
    transactions: int


class IncomeChartResponse(BaseModel):
    period: str
    date_from: date
    date_to: date
    total_income: int
    points: list[IncomePointResponse]

    @classmethod
    def build(cls, chart: IncomeChart) -> "IncomeChartResponse":
        return cls(
            period=chart.period.value,
            date_from=chart.date_from,
            date_to=chart.date_to,
            total_income=chart.total_income,
            points=[IncomePointResponse(**p.__dict__) for p in chart.points],
        )
