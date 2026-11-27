from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "c3e8d41f7a52"
down_revision: Union[str, None] = "b7c2e91f4a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("deleted_at", mysql.DATETIME(fsp=3), nullable=True))
    op.drop_constraint("ck_messages_text_required", "messages", type_="check")
    op.create_check_constraint(
        "ck_messages_text_required",
        "messages",
        "message_type <> 'TEXT' OR message_text IS NOT NULL OR deleted_at IS NOT NULL",
    )
    op.create_table(
        "hidden_messages",
        sa.Column("message_id", sa.CHAR(36), sa.ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.CHAR(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("hidden_at", mysql.DATETIME(fsp=3), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP(3)")),
    )


def downgrade() -> None:
    op.drop_table("hidden_messages")
    op.execute("UPDATE messages SET message_text = '' WHERE message_type = 'TEXT' AND message_text IS NULL")
    op.drop_constraint("ck_messages_text_required", "messages", type_="check")
    op.create_check_constraint(
        "ck_messages_text_required", "messages", "message_type <> 'TEXT' OR message_text IS NOT NULL"
    )
    op.drop_column("messages", "deleted_at")
