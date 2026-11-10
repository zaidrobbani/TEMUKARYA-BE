"""Kolom tambahan untuk workflow, pembayaran, review hasil, dan ulasan sesuai Figma.

Revision ID: 17a58015bd8b
Revises: a1d4e7c29b63
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "17a58015bd8b"
down_revision: Union[str, None] = "a1d4e7c29b63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("transaction_number", sa.String(30), nullable=True))
    op.add_column("payments", sa.Column("expires_at", mysql.DATETIME(fsp=3), nullable=True))
    op.create_unique_constraint("uq_payments_transaction_number", "payments", ["transaction_number"])

    op.add_column("project_agreements", sa.Column("change_request_note", sa.Text(), nullable=True))
    op.add_column("project_agreements", sa.Column("change_requested_at", mysql.DATETIME(fsp=3), nullable=True))

    op.add_column("project_status_history", sa.Column("reason_code", sa.String(40), nullable=True))

    op.add_column("submission_reviews", sa.Column("focus_areas", sa.JSON(), nullable=True))
    op.add_column("submission_reviews", sa.Column("revision_items", sa.JSON(), nullable=True))

    op.add_column("freelancer_reviews", sa.Column("highlights", sa.JSON(), nullable=True))

    op.create_index("ix_notifications_user_read_at", "notifications", ["user_id", "read_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_user_read_at", table_name="notifications")
    op.drop_column("freelancer_reviews", "highlights")
    op.drop_column("submission_reviews", "revision_items")
    op.drop_column("submission_reviews", "focus_areas")
    op.drop_column("project_status_history", "reason_code")
    op.drop_column("project_agreements", "change_requested_at")
    op.drop_column("project_agreements", "change_request_note")
    op.drop_constraint("uq_payments_transaction_number", "payments", type_="unique")
    op.drop_column("payments", "expires_at")
    op.drop_column("payments", "transaction_number")
