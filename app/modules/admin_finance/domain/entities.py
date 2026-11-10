from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from app.modules.payments.domain.entities import Payment, PaymentAttempt


class IncomePeriod(StrEnum):
    DAY = "DAY"
    MONTH = "MONTH"


@dataclass(frozen=True)
class FinanceSummary:
    total_income: int
    income_this_month: int
    total_paid_amount: int
    held_amount: int
    released_amount: int
    successful_transactions: int
    pending_transactions: int
    failed_transactions: int
    cancelled_transactions: int
    total_transactions: int


@dataclass(frozen=True)
class AdminTransaction:
    payment: Payment
    project_id: str
    project_title: str
    project_status: str
    umkm_id: str
    umkm_name: str
    umkm_business_name: str | None
    freelancer_id: str
    freelancer_name: str


@dataclass(frozen=True)
class AdminTransactionDetail:
    transaction: AdminTransaction
    attempts: list[PaymentAttempt]


@dataclass(frozen=True)
class TransactionFilter:
    status: str | None = None
    fund_status: str | None = None
    search: str | None = None
    paid_from: datetime | None = None
    paid_to: datetime | None = None


@dataclass(frozen=True)
class PaidRow:
    paid_at: datetime
    platform_fee_amount: int
    gross_amount: int


@dataclass(frozen=True)
class IncomePoint:
    period_start: date
    label: str
    income: int
    gross_amount: int
    transactions: int
