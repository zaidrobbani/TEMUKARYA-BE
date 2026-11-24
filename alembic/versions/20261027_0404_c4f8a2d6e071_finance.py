from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = 'c4f8a2d6e071'
down_revision: Union[str, None] = '1e5a7c9b3d26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def uuid_pk() -> sa.Column:
    return sa.Column("id", sa.CHAR(36), primary_key=True, server_default=sa.text("(UUID())"))


def uuid_fk(name: str, target: str, *, nullable: bool = False, ondelete: str = "RESTRICT") -> sa.Column:
    return sa.Column(name, sa.CHAR(36), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def timestamp(name: str, *, on_update: bool = False) -> sa.Column:
    default = "CURRENT_TIMESTAMP(3)" + (" ON UPDATE CURRENT_TIMESTAMP(3)" if on_update else "")
    return sa.Column(name, mysql.DATETIME(fsp=3), nullable=False, server_default=sa.text(default))


def upgrade() -> None:
    op.create_table(
        "payments",
        uuid_pk(),
        uuid_fk("agreement_id", "project_agreements.id"),
        sa.Column("gross_amount", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("platform_fee_amount", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("freelancer_amount", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False, server_default="QRIS_SIMULATION"),
        sa.Column("status", sa.String(20), nullable=False, server_default="MENUNGGU"),
        sa.Column("fund_status", sa.String(20), nullable=True),
        sa.Column("paid_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.Column("released_at", mysql.DATETIME(fsp=3), nullable=True),
        timestamp("created_at"),
        timestamp("updated_at", on_update=True),
        sa.UniqueConstraint("agreement_id", name="uq_payments_agreement"),
        sa.CheckConstraint("gross_amount > 0", name="ck_payments_gross_positive"),
        sa.CheckConstraint(
            "platform_fee_amount + freelancer_amount = gross_amount", name="ck_payments_amount_split"
        ),
        sa.CheckConstraint("fund_status IS NULL OR status = 'BERHASIL'", name="ck_payments_fund_requires_paid"),
        sa.CheckConstraint(
            "fund_status IS NULL OR fund_status IN ('HELD', 'RELEASED')", name="ck_payments_fund_status_values"
        ),
    )

    op.create_table(
        "payment_attempts",
        uuid_pk(),
        uuid_fk("payment_id", "payments.id"),
        sa.Column("attempt_number", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        timestamp("attempted_at"),
        sa.Column("completed_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.UniqueConstraint("payment_id", "attempt_number", name="uq_payment_attempts_payment_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_payment_attempts_idempotency_key"),
    )

    op.create_table(
        "wallets",
        uuid_pk(),
        uuid_fk("freelancer_id", "freelancer_profiles.user_id"),
        timestamp("created_at"),
        timestamp("updated_at", on_update=True),
        sa.UniqueConstraint("freelancer_id", name="uq_wallets_freelancer"),
    )

    op.create_table(
        "wallet_transactions",
        uuid_pk(),
        uuid_fk("wallet_id", "wallets.id"),
        uuid_fk("payment_id", "payments.id"),
        sa.Column("transaction_type", sa.String(30), nullable=False),
        sa.Column("balance_type", sa.String(20), nullable=False),
        sa.Column("amount_delta", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.String(400), nullable=True),
        timestamp("created_at"),
        sa.UniqueConstraint(
            "payment_id", "transaction_type", "balance_type", name="uq_wallet_transactions_payment_event"
        ),
        sa.CheckConstraint("amount_delta <> 0", name="ck_wallet_transactions_nonzero"),
        sa.CheckConstraint("balance_type IN ('HELD', 'AVAILABLE')", name="ck_wallet_transactions_balance_type"),
    )
    op.create_index("ix_wallet_transactions_wallet_created_at", "wallet_transactions", ["wallet_id", "created_at"])


def downgrade() -> None:
    op.drop_table("wallet_transactions")
    op.drop_table("wallets")
    op.drop_table("payment_attempts")
    op.drop_table("payments")
