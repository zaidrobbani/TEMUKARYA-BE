from datetime import datetime
from uuid import uuid4

from sqlalchemy import exists, func, insert, select, text
from sqlalchemy.orm import Session

from app.core.database import from_db_utc, to_db_utc
from app.modules.payments.domain.entities import (
    BalanceType,
    FundStatus,
    Payment,
    PaymentAttempt,
    PaymentHistoryItem,
    TransactionGroup,
    Wallet,
    WalletBalance,
    WalletEntry,
    WalletEntryFilter,
    WalletEntryType,
    WalletTransaction,
    WalletTransactionType,
)
from app.modules.payments.domain.repositories import PaymentRepository, WalletRepository
from app.modules.payments.infrastructure.models import (
    PaymentAttemptModel,
    PaymentModel,
    WalletModel,
    WalletTransactionModel,
)


def _utc(value: datetime | None) -> datetime | None:
    return from_db_utc(value) if value is not None else None


def _db(value: datetime | None) -> datetime | None:
    return to_db_utc(value) if value is not None else None


def to_payment(model: PaymentModel) -> Payment:
    return Payment(
        id=model.id,
        agreement_id=model.agreement_id,
        gross_amount=int(model.gross_amount),
        platform_fee_amount=int(model.platform_fee_amount),
        freelancer_amount=int(model.freelancer_amount),
        payment_method=model.payment_method,
        status=model.status,
        created_at=_utc(model.created_at),
        fund_status=model.fund_status,
        paid_at=_utc(model.paid_at),
        released_at=_utc(model.released_at),
        transaction_number=model.transaction_number,
        expires_at=_utc(model.expires_at),
        updated_at=_utc(model.updated_at),
    )


def to_attempt(model: PaymentAttemptModel) -> PaymentAttempt:
    return PaymentAttempt(
        id=model.id,
        payment_id=model.payment_id,
        attempt_number=int(model.attempt_number),
        status=model.status,
        attempted_at=_utc(model.attempted_at),
        idempotency_key=model.idempotency_key,
        failure_reason=model.failure_reason,
        completed_at=_utc(model.completed_at),
    )


# Kondisi tab Riwayat Transaksi; p = payments.
GROUP_CONDITIONS = {
    TransactionGroup.ALL: "1 = 1",
    TransactionGroup.PENDING: "p.status IN ('MENUNGGU', 'GAGAL')",
    TransactionGroup.HELD: "p.status = 'BERHASIL' AND p.fund_status = 'HELD'",
    TransactionGroup.COMPLETED: "p.status = 'BERHASIL' AND p.fund_status = 'RELEASED'",
    TransactionGroup.CANCELLED: "p.status = 'DIBATALKAN'",
}

_HISTORY_FROM = """
    FROM payments p
    JOIN project_agreements a ON a.id = p.agreement_id
    JOIN projects pr ON pr.id = a.project_id
    JOIN users fu ON fu.id = a.freelancer_id
    WHERE pr.umkm_id = :uid
"""

_SEARCH = " AND (pr.title LIKE :search OR p.transaction_number LIKE :search OR fu.name LIKE :search)"


def _like(search: str) -> str:
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class SqlAlchemyPaymentRepository(PaymentRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_agreement(self, agreement_id: str, lock: bool = False) -> Payment | None:
        query = select(PaymentModel).where(PaymentModel.agreement_id == agreement_id)
        if lock:
            query = query.with_for_update()
        model = self._session.scalar(query.execution_options(populate_existing=True))
        return to_payment(model) if model else None

    def add(self, payment: Payment) -> None:
        self._session.add(
            PaymentModel(
                id=payment.id,
                agreement_id=payment.agreement_id,
                gross_amount=payment.gross_amount,
                platform_fee_amount=payment.platform_fee_amount,
                freelancer_amount=payment.freelancer_amount,
                payment_method=payment.payment_method,
                status=payment.status,
                fund_status=payment.fund_status,
                created_at=to_db_utc(payment.created_at),
                expires_at=_db(payment.expires_at),
            )
        )
        self._session.flush()

    def update(self, payment: Payment) -> None:
        model = self._session.get(PaymentModel, payment.id)
        model.gross_amount = payment.gross_amount
        model.platform_fee_amount = payment.platform_fee_amount
        model.freelancer_amount = payment.freelancer_amount
        model.status = payment.status
        model.fund_status = payment.fund_status
        model.paid_at = _db(payment.paid_at)
        model.released_at = _db(payment.released_at)
        model.transaction_number = payment.transaction_number
        model.expires_at = _db(payment.expires_at)
        self._session.flush()

    def next_attempt_number(self, payment_id: str) -> int:
        current = self._session.scalar(
            select(func.max(PaymentAttemptModel.attempt_number)).where(PaymentAttemptModel.payment_id == payment_id)
        )
        return int(current or 0) + 1

    def add_attempt(self, attempt: PaymentAttempt) -> None:
        self._session.add(
            PaymentAttemptModel(
                id=attempt.id,
                payment_id=attempt.payment_id,
                attempt_number=attempt.attempt_number,
                idempotency_key=attempt.idempotency_key,
                status=attempt.status,
                failure_reason=attempt.failure_reason,
                attempted_at=to_db_utc(attempt.attempted_at),
                completed_at=_db(attempt.completed_at),
            )
        )
        self._session.flush()

    def get_attempt_by_key(self, idempotency_key: str) -> PaymentAttempt | None:
        model = self._session.scalar(
            select(PaymentAttemptModel).where(PaymentAttemptModel.idempotency_key == idempotency_key)
        )
        return to_attempt(model) if model else None

    def list_attempts(self, payment_id: str) -> list[PaymentAttempt]:
        rows = self._session.scalars(
            select(PaymentAttemptModel)
            .where(PaymentAttemptModel.payment_id == payment_id)
            .order_by(PaymentAttemptModel.attempt_number)
        )
        return [to_attempt(m) for m in rows]

    def transaction_number_exists(self, number: str) -> bool:
        return bool(self._session.scalar(select(exists().where(PaymentModel.transaction_number == number))))

    def list_umkm_history(
        self, umkm_id: str, group: TransactionGroup, search: str | None, limit: int, offset: int
    ) -> list[PaymentHistoryItem]:
        sql = (
            "SELECT p.id AS payment_id, pr.id AS project_id, pr.title, fu.id AS freelancer_id, fu.name "
            + _HISTORY_FROM
            + f" AND {GROUP_CONDITIONS[group]}"
            + (_SEARCH if search else "")
            + " ORDER BY COALESCE(p.paid_at, p.created_at) DESC, p.id LIMIT :limit OFFSET :offset"
        )
        params = {"uid": umkm_id, "limit": limit, "offset": offset}
        if search:
            params["search"] = _like(search)
        rows = self._session.execute(text(sql), params).mappings().all()
        if not rows:
            return []
        models = {
            m.id: m
            for m in self._session.scalars(
                select(PaymentModel).where(PaymentModel.id.in_([r["payment_id"] for r in rows]))
            )
        }
        return [
            PaymentHistoryItem(
                payment=to_payment(models[r["payment_id"]]),
                project_id=r["project_id"],
                project_title=r["title"],
                freelancer_id=r["freelancer_id"],
                freelancer_name=r["name"],
            )
            for r in rows
        ]

    def count_umkm_history(self, umkm_id: str, search: str | None) -> dict[str, int]:
        columns = ", ".join(
            f"COALESCE(SUM(CASE WHEN {condition} THEN 1 ELSE 0 END), 0) AS `{group.value}`"
            for group, condition in GROUP_CONDITIONS.items()
        )
        params = {"uid": umkm_id}
        if search:
            params["search"] = _like(search)
        row = self._session.execute(
            text(f"SELECT {columns} " + _HISTORY_FROM + (_SEARCH if search else "")), params
        ).mappings().one()
        return {group.value: int(row[group.value]) for group in TransactionGroup}


class SqlAlchemyWalletRepository(WalletRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_wallet(self, freelancer_id: str) -> Wallet | None:
        model = self._session.scalar(select(WalletModel).where(WalletModel.freelancer_id == freelancer_id))
        return Wallet(model.id, model.freelancer_id) if model else None

    def get_or_create_wallet(self, freelancer_id: str, now: datetime) -> Wallet:
        # INSERT IGNORE: dua pembayaran pertama yang bersamaan tidak saling menggagalkan.
        self._session.execute(
            insert(WalletModel)
            .prefix_with("IGNORE")
            .values(id=str(uuid4()), freelancer_id=freelancer_id, created_at=to_db_utc(now))
        )
        model = self._session.scalar(
            select(WalletModel).where(WalletModel.freelancer_id == freelancer_id).with_for_update()
        )
        return Wallet(model.id, model.freelancer_id)

    def add_transaction(self, transaction: WalletTransaction) -> None:
        self._session.add(
            WalletTransactionModel(
                id=transaction.id,
                wallet_id=transaction.wallet_id,
                payment_id=transaction.payment_id,
                transaction_type=transaction.transaction_type,
                balance_type=transaction.balance_type,
                amount_delta=transaction.amount_delta,
                description=transaction.description,
                created_at=to_db_utc(transaction.created_at),
            )
        )
        self._session.flush()

    def balance(self, wallet_id: str) -> WalletBalance:
        rows = self._session.execute(
            select(WalletTransactionModel.balance_type, func.sum(WalletTransactionModel.amount_delta))
            .where(WalletTransactionModel.wallet_id == wallet_id)
            .group_by(WalletTransactionModel.balance_type)
        ).all()
        totals = {row[0]: int(row[1] or 0) for row in rows}
        return WalletBalance(held=totals.get(BalanceType.HELD, 0), available=totals.get(BalanceType.AVAILABLE, 0))

    def list_entries(
        self, wallet_id: str, entry_filter: WalletEntryFilter, limit: int, offset: int
    ) -> list[WalletEntry]:
        visible = {
            WalletEntryFilter.ALL: "((t.transaction_type = :held_type AND t.balance_type = 'HELD') "
            "OR (t.transaction_type = :released_type AND t.balance_type = 'AVAILABLE'))",
            WalletEntryFilter.HELD: "t.transaction_type = :held_type AND t.balance_type = 'HELD' "
            "AND p.fund_status = 'HELD'",
            WalletEntryFilter.INCOME: "t.transaction_type = :released_type AND t.balance_type = 'AVAILABLE'",
        }[entry_filter]
        rows = self._session.execute(
            text(
                "SELECT t.id, t.transaction_type, t.payment_id, t.amount_delta, t.created_at, "
                "p.fund_status, pr.id AS project_id, pr.title "
                "FROM wallet_transactions t "
                "JOIN payments p ON p.id = t.payment_id "
                "JOIN project_agreements a ON a.id = p.agreement_id "
                "JOIN projects pr ON pr.id = a.project_id "
                f"WHERE t.wallet_id = :wid AND {visible} "
                "ORDER BY t.created_at DESC, t.id LIMIT :limit OFFSET :offset"
            ),
            {
                "wid": wallet_id,
                "held_type": WalletTransactionType.PAYMENT_HELD.value,
                "released_type": WalletTransactionType.FUND_RELEASED.value,
                "limit": limit,
                "offset": offset,
            },
        ).mappings().all()
        return [
            WalletEntry(
                id=r["id"],
                entry_type=WalletEntryType.FUND_HELD
                if r["transaction_type"] == WalletTransactionType.PAYMENT_HELD
                else WalletEntryType.FUND_RELEASED,
                payment_id=r["payment_id"],
                project_id=r["project_id"],
                project_title=r["title"],
                amount=int(r["amount_delta"]),
                created_at=_utc(r["created_at"]),
                still_held=r["fund_status"] == FundStatus.HELD,
            )
            for r in rows
        ]

