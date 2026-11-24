import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.modules.workflow.domain.entities import wib_date

COMMISSION_PERCENT = 5
QRIS_TTL = timedelta(minutes=15)


class PaymentStatus(StrEnum):
    MENUNGGU = "MENUNGGU"
    BERHASIL = "BERHASIL"
    GAGAL = "GAGAL"
    DIBATALKAN = "DIBATALKAN"


PAYMENT_STATUS_LABELS = {
    PaymentStatus.MENUNGGU: "Menunggu pembayaran",
    PaymentStatus.BERHASIL: "Pembayaran berhasil",
    PaymentStatus.GAGAL: "Pembayaran gagal",
    PaymentStatus.DIBATALKAN: "Dibatalkan",
}


class FundStatus(StrEnum):
    HELD = "HELD"
    RELEASED = "RELEASED"


FUND_STATUS_LABELS = {
    FundStatus.HELD: "Dana ditahan",
    FundStatus.RELEASED: "Dana diteruskan",
}


class AttemptStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class PaymentOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class PaymentMethod(StrEnum):
    QRIS_SIMULATION = "QRIS_SIMULATION"


PAYMENT_METHOD_LABELS = {PaymentMethod.QRIS_SIMULATION: "QRIS (simulasi)"}


class WalletTransactionType(StrEnum):
    PAYMENT_HELD = "PAYMENT_HELD"
    FUND_RELEASED = "FUND_RELEASED"


class BalanceType(StrEnum):
    HELD = "HELD"
    AVAILABLE = "AVAILABLE"


class TransactionGroup(StrEnum):
    """Tab Riwayat Transaksi UMKM."""

    ALL = "ALL"
    PENDING = "PENDING"
    HELD = "HELD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DisplayStatus(StrEnum):
    MENUNGGU_PEMBAYARAN = "MENUNGGU_PEMBAYARAN"
    GAGAL = "GAGAL"
    DANA_DITAHAN = "DANA_DITAHAN"
    SELESAI = "SELESAI"
    DIBATALKAN = "DIBATALKAN"


DISPLAY_STATUS_LABELS = {
    DisplayStatus.MENUNGGU_PEMBAYARAN: "Menunggu Pembayaran",
    DisplayStatus.GAGAL: "Pembayaran Gagal",
    DisplayStatus.DANA_DITAHAN: "Dana Ditahan",
    DisplayStatus.SELESAI: "Selesai",
    DisplayStatus.DIBATALKAN: "Dibatalkan",
}


class WalletEntryType(StrEnum):
    FUND_HELD = "FUND_HELD"
    FUND_RELEASED = "FUND_RELEASED"


WALLET_ENTRY_LABELS = {
    WalletEntryType.FUND_HELD: "Dana ditahan",
    WalletEntryType.FUND_RELEASED: "Pemasukan project",
}


class WalletEntryFilter(StrEnum):
    ALL = "ALL"
    HELD = "HELD"
    INCOME = "INCOME"


def split_amount(gross_amount: int) -> tuple[int, int]:
    """(komisi, hak freelancer). Komisi = floor(nilai * 5 / 100)."""
    if type(gross_amount) is not int or gross_amount <= 0:
        raise ValueError("Nilai proyek harus bilangan bulat lebih dari nol")
    fee = gross_amount * COMMISSION_PERCENT // 100
    return fee, gross_amount - fee


def generate_transaction_number(paid_at: datetime) -> str:
    return f"TMK-{wib_date(paid_at):%Y%m%d}-{secrets.randbelow(100_000):05d}"


@dataclass(frozen=True)
class Payment:
    id: str
    agreement_id: str
    gross_amount: int
    platform_fee_amount: int
    freelancer_amount: int
    payment_method: str
    status: str
    created_at: datetime
    fund_status: str | None = None
    paid_at: datetime | None = None
    released_at: datetime | None = None
    transaction_number: str | None = None
    expires_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def display_status(self) -> DisplayStatus:
        if self.status == PaymentStatus.BERHASIL:
            return DisplayStatus.SELESAI if self.fund_status == FundStatus.RELEASED else DisplayStatus.DANA_DITAHAN
        if self.status == PaymentStatus.GAGAL:
            return DisplayStatus.GAGAL
        if self.status == PaymentStatus.DIBATALKAN:
            return DisplayStatus.DIBATALKAN
        return DisplayStatus.MENUNGGU_PEMBAYARAN

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and now >= self.expires_at


@dataclass(frozen=True)
class PaymentAttempt:
    id: str
    payment_id: str
    attempt_number: int
    status: str
    attempted_at: datetime
    idempotency_key: str | None = None
    failure_reason: str | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class Wallet:
    id: str
    freelancer_id: str


@dataclass(frozen=True)
class WalletTransaction:
    id: str
    wallet_id: str
    payment_id: str
    transaction_type: str
    balance_type: str
    amount_delta: int
    created_at: datetime
    description: str | None = None


@dataclass(frozen=True)
class WalletBalance:
    held: int = 0
    available: int = 0

    @property
    def total(self) -> int:
        return self.held + self.available


@dataclass(frozen=True)
class WalletEntry:
    id: str
    entry_type: WalletEntryType
    payment_id: str
    project_id: str
    project_title: str
    amount: int
    created_at: datetime
    still_held: bool


@dataclass(frozen=True)
class PaymentHistoryItem:
    payment: Payment
    project_id: str
    project_title: str
    freelancer_id: str
    freelancer_name: str
