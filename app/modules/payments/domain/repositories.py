from abc import ABC, abstractmethod
from datetime import datetime

from app.modules.payments.domain.entities import (
    Payment,
    PaymentAttempt,
    PaymentHistoryItem,
    TransactionGroup,
    Wallet,
    WalletBalance,
    WalletEntry,
    WalletEntryFilter,
    WalletTransaction,
)


class PaymentRepository(ABC):
    @abstractmethod
    def get_by_agreement(self, agreement_id: str, lock: bool = False) -> Payment | None: ...

    @abstractmethod
    def add(self, payment: Payment) -> None: ...

    @abstractmethod
    def update(self, payment: Payment) -> None: ...

    @abstractmethod
    def next_attempt_number(self, payment_id: str) -> int: ...

    @abstractmethod
    def add_attempt(self, attempt: PaymentAttempt) -> None: ...

    @abstractmethod
    def get_attempt_by_key(self, idempotency_key: str) -> PaymentAttempt | None: ...

    @abstractmethod
    def list_attempts(self, payment_id: str) -> list[PaymentAttempt]:
        """Urut dari percobaan pertama."""

    @abstractmethod
    def transaction_number_exists(self, number: str) -> bool: ...

    @abstractmethod
    def list_umkm_history(
        self, umkm_id: str, group: TransactionGroup, search: str | None, limit: int, offset: int
    ) -> list[PaymentHistoryItem]:
        """Urut dari waktu bayar/dibuat terbaru."""

    @abstractmethod
    def count_umkm_history(self, umkm_id: str, search: str | None) -> dict[str, int]:
        """Jumlah per TransactionGroup (termasuk ALL)."""


class WalletRepository(ABC):
    @abstractmethod
    def get_wallet(self, freelancer_id: str) -> Wallet | None: ...

    @abstractmethod
    def get_or_create_wallet(self, freelancer_id: str, now: datetime) -> Wallet:
        """Dibuat lazy saat pembayaran pertama; aman dipanggil bersamaan."""

    @abstractmethod
    def add_transaction(self, transaction: WalletTransaction) -> None: ...

    @abstractmethod
    def balance(self, wallet_id: str) -> WalletBalance: ...

    @abstractmethod
    def list_entries(
        self, wallet_id: str, entry_filter: WalletEntryFilter, limit: int, offset: int
    ) -> list[WalletEntry]:
        """Urut terbaru dulu. Baris debit HELD saat pelepasan tidak ditampilkan."""
