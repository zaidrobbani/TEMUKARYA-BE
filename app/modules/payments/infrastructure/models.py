from datetime import datetime

from sqlalchemy import BigInteger, CHAR, CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UpdatedAt, UuidPk
from app.modules.workflow.infrastructure import models as _workflow_models  # noqa: F401


class PaymentModel(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("agreement_id", name="uq_payments_agreement"),
        UniqueConstraint("transaction_number", name="uq_payments_transaction_number"),
        CheckConstraint("gross_amount > 0", name="ck_payments_gross_positive"),
        CheckConstraint("platform_fee_amount + freelancer_amount = gross_amount", name="ck_payments_amount_split"),
        CheckConstraint("fund_status IS NULL OR status = 'BERHASIL'", name="ck_payments_fund_requires_paid"),
        CheckConstraint(
            "fund_status IS NULL OR fund_status IN ('HELD', 'RELEASED')", name="ck_payments_fund_status_values"
        ),
    )

    id: Mapped[UuidPk]
    agreement_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("project_agreements.id", ondelete="RESTRICT"))
    gross_amount: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True))
    platform_fee_amount: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True))
    freelancer_amount: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True))
    payment_method: Mapped[str] = mapped_column(String(30), server_default=text("'QRIS_SIMULATION'"))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'MENUNGGU'"))
    fund_status: Mapped[str | None] = mapped_column(String(20))
    paid_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=3))
    released_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=3))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    transaction_number: Mapped[str | None] = mapped_column(String(30))
    expires_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=3))


class PaymentAttemptModel(Base):
    __tablename__ = "payment_attempts"
    __table_args__ = (
        UniqueConstraint("payment_id", "attempt_number", name="uq_payment_attempts_payment_number"),
        UniqueConstraint("idempotency_key", name="uq_payment_attempts_idempotency_key"),
    )

    id: Mapped[UuidPk]
    payment_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("payments.id", ondelete="RESTRICT"))
    attempt_number: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'PENDING'"))
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    attempted_at: Mapped[CreatedAt]
    completed_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=3))


class WalletModel(Base):
    __tablename__ = "wallets"
    __table_args__ = (UniqueConstraint("freelancer_id", name="uq_wallets_freelancer"),)

    id: Mapped[UuidPk]
    freelancer_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("freelancer_profiles.user_id", ondelete="RESTRICT")
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class WalletTransactionModel(Base):
    __tablename__ = "wallet_transactions"
    __table_args__ = (
        UniqueConstraint(
            "payment_id", "transaction_type", "balance_type", name="uq_wallet_transactions_payment_event"
        ),
        CheckConstraint("amount_delta <> 0", name="ck_wallet_transactions_nonzero"),
        CheckConstraint("balance_type IN ('HELD', 'AVAILABLE')", name="ck_wallet_transactions_balance_type"),
        Index("ix_wallet_transactions_wallet_created_at", "wallet_id", "created_at"),
    )

    id: Mapped[UuidPk]
    wallet_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("wallets.id", ondelete="RESTRICT"))
    payment_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("payments.id", ondelete="RESTRICT"))
    transaction_type: Mapped[str] = mapped_column(String(30))
    balance_type: Mapped[str] = mapped_column(String(20))
    amount_delta: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str | None] = mapped_column(String(400))
    created_at: Mapped[CreatedAt]
