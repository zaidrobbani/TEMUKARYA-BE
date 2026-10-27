"""communication: conversations, messages, message attachments, notifications

Revision ID: 1e5a7c9b3d26
Revises: b7c1e9d3f582
Create Date: 2026-10-27 04:03:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = '1e5a7c9b3d26'
down_revision: Union[str, None] = 'b7c1e9d3f582'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def uuid_pk() -> sa.Column:
    return sa.Column("id", sa.CHAR(36), primary_key=True, server_default=sa.text("(UUID())"))


def uuid_fk(name: str, target: str, *, nullable: bool = False, ondelete: str = "RESTRICT") -> sa.Column:
    return sa.Column(name, sa.CHAR(36), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def timestamp(name: str, *, on_update: bool = False) -> sa.Column:
    default = "CURRENT_TIMESTAMP(3)" + (" ON UPDATE CURRENT_TIMESTAMP(3)" if on_update else "")
    return sa.Column(name, mysql.DATETIME(fsp=3), nullable=False, server_default=sa.text(default))


def file_columns() -> list[sa.Column]:
    return [
        sa.Column("original_file_name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", mysql.BIGINT(unsigned=True), nullable=False),
        timestamp("uploaded_at"),
    ]


def upgrade() -> None:
    op.create_table(
        "conversations",
        uuid_pk(),
        uuid_fk("umkm_id", "umkm_profiles.user_id"),
        uuid_fk("freelancer_id", "freelancer_profiles.user_id"),
        # NULL = chat umum sebelum ada project (dari pencarian freelancer manual)
        uuid_fk("project_id", "projects.id", nullable=True),
        # UNIQUE biasa membolehkan banyak NULL, jadi project_id NULL dipetakan ke '' agar
        # satu pasangan UMKM–freelancer hanya punya satu chat umum dan satu chat per project.
        sa.Column("project_key", sa.CHAR(36), sa.Computed("coalesce(project_id, '')", persisted=True)),
        sa.Column("last_message_at", mysql.DATETIME(fsp=3), nullable=True),
        timestamp("created_at"),
        timestamp("updated_at", on_update=True),
        sa.UniqueConstraint("umkm_id", "freelancer_id", "project_key", name="uq_conversations_participants_project"),
    )
    op.create_index("ix_conversations_umkm_last_message", "conversations", ["umkm_id", "last_message_at"])
    op.create_index("ix_conversations_freelancer_last_message", "conversations", ["freelancer_id", "last_message_at"])

    op.create_table(
        "messages",
        uuid_pk(),
        uuid_fk("conversation_id", "conversations.id"),
        # Harus salah satu peserta conversation; divalidasi di backend
        uuid_fk("sender_user_id", "users.id"),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("message_type", sa.String(20), nullable=False, server_default="TEXT"),
        timestamp("sent_at"),
        sa.Column("read_at", mysql.DATETIME(fsp=3), nullable=True),
        timestamp("created_at"),
        sa.CheckConstraint(
            "message_type <> 'TEXT' OR message_text IS NOT NULL", name="ck_messages_text_required"
        ),
    )
    # UUID acak tidak berurutan, jadi urutan pesan selalu memakai sent_at (presisi milidetik)
    op.create_index("ix_messages_conversation_sent_at", "messages", ["conversation_id", "sent_at"])

    op.create_table(
        "message_attachments",
        uuid_pk(),
        uuid_fk("message_id", "messages.id", ondelete="CASCADE"),
        *file_columns(),
    )

    op.create_table(
        "notifications",
        uuid_pk(),
        uuid_fk("user_id", "users.id", ondelete="CASCADE"),
        sa.Column("notification_type", sa.String(45), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        # Objek yang dibuka saat notifikasi diklik, misalnya ("PROJECT", <project_id>)
        sa.Column("reference_type", sa.String(40), nullable=True),
        sa.Column("reference_id", sa.CHAR(36), nullable=True),
        timestamp("created_at"),
        sa.Column("read_at", mysql.DATETIME(fsp=3), nullable=True),
    )
    op.create_index("ix_notifications_user_created_at", "notifications", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("message_attachments")
    op.drop_table("messages")
    op.drop_table("conversations")
