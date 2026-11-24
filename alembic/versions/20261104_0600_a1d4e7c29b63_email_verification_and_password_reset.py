from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = 'a1d4e7c29b63'
down_revision: Union[str, None] = '5b8d3f1a9e27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", mysql.DATETIME(fsp=3), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", mysql.DATETIME(fsp=3), nullable=True))
    op.add_column("users", sa.Column("terms_accepted_at", mysql.DATETIME(fsp=3), nullable=True))
    op.execute("UPDATE users SET email_verified_at = created_at")

    op.create_table(
        "auth_action_tokens",
        sa.Column("id", sa.CHAR(36), primary_key=True, server_default=sa.text("(UUID())")),
        sa.Column(
            "user_id",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("token_hash", sa.CHAR(64), nullable=False),
        sa.Column("expires_at", mysql.DATETIME(fsp=3), nullable=False),
        sa.Column("used_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=3),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
        ),
        sa.UniqueConstraint("token_hash", name="uq_auth_action_tokens_token_hash"),
    )
    op.create_index(
        "ix_auth_action_tokens_user_purpose_created",
        "auth_action_tokens",
        ["user_id", "purpose", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("auth_action_tokens")
    op.drop_column("users", "terms_accepted_at")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "email_verified_at")
