from datetime import datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Computed,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConversationModel(Base):
    __tablename__ = "conversations"

    __table_args__ = (
        UniqueConstraint(
            "umkm_id",
            "freelancer_id",
            "project_key",
            name="uq_conversations_participants_project",
        ),
        Index(
            "ix_conversations_umkm_last_message",
            "umkm_id",
            "last_message_at",
        ),
        Index(
            "ix_conversations_freelancer_last_message",
            "freelancer_id",
            "last_message_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        server_default=text("(UUID())"),
    )

    umkm_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey(
            "umkm_profiles.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    freelancer_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey(
            "freelancer_profiles.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    project_id: Mapped[str | None] = mapped_column(
        CHAR(36),
        ForeignKey(
            "projects.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    project_key: Mapped[str] = mapped_column(
        CHAR(36),
        Computed(
            "coalesce(project_id, '')",
            persisted=True,
        ),
        nullable=True,
    )

    last_message_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=False,
        server_default=text(
            "CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"
        ),
    )


class MessageModel(Base):
    __tablename__ = "messages"

    __table_args__ = (
        CheckConstraint(
            "message_type <> 'TEXT' OR message_text IS NOT NULL OR deleted_at IS NOT NULL",
            name="ck_messages_text_required",
        ),
        Index(
            "ix_messages_conversation_sent_at",
            "conversation_id",
            "sent_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        server_default=text("(UUID())"),
    )

    conversation_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey(
            "conversations.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    sender_user_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    message_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'TEXT'"),
    )

    sent_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )

    read_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=True,
    )


class HiddenMessageModel(Base):
    __tablename__ = "hidden_messages"

    message_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    hidden_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )


class MessageAttachmentModel(Base):
    __tablename__ = "message_attachments"

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        server_default=text("(UUID())"),
    )

    message_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey(
            "messages.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    original_file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        nullable=False,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )
