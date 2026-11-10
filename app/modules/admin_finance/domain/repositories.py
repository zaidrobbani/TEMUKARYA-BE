from abc import ABC, abstractmethod
from datetime import datetime

from app.modules.admin_finance.domain.entities import (
    AdminTransaction,
    AdminTransactionDetail,
    FinanceSummary,
    PaidRow,
    TransactionFilter,
)


class AdminFinanceRepository(ABC):
    @abstractmethod
    def summary(self, month_start: datetime, month_end: datetime) -> FinanceSummary:
        """month_start/month_end (UTC) untuk income_this_month."""

    @abstractmethod
    def list_transactions(self, filters: TransactionFilter, limit: int, offset: int) -> list[AdminTransaction]:
        """Urut terbaru (paid_at, lalu created_at)."""

    @abstractmethod
    def count_transactions(self, filters: TransactionFilter) -> int: ...

    @abstractmethod
    def get_transaction(self, payment_id: str) -> AdminTransactionDetail | None: ...

    @abstractmethod
    def paid_rows(self, start: datetime, end: datetime) -> list[PaidRow]:
        """Pembayaran BERHASIL dengan paid_at di [start, end)."""
