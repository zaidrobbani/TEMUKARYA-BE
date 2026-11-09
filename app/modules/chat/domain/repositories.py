from datetime import datetime
from typing import Protocol

from app.modules.chat.domain.entities import (
    Conversation,
    Message,
    MessageAttachment,
)


# ============================================================
# 1. CONVERSATION REPOSITORY CONTRACT
# ============================================================

class ConversationRepository(Protocol):
    """
    Interface untuk mengakses data percakapan.

    Implementasi SQLAlchemy akan dibuat
    pada Infrastructure Layer.
    """

    # --------------------------------------------------------
    # Find existing conversation
    # --------------------------------------------------------

    def find_by_participants(
        self,
        umkm_id: str,
        freelancer_id: str,
        project_id: str | None,
    ) -> Conversation | None:
        ...

    # --------------------------------------------------------
    # Get conversation by ID
    # --------------------------------------------------------

    def get_by_id(
        self,
        conversation_id: str,
    ) -> Conversation | None:
        ...

    # --------------------------------------------------------
    # List conversations for a user
    # --------------------------------------------------------

    def list_for_user(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[Conversation, ...]:
        ...

    # --------------------------------------------------------
    # Verify user role
    # --------------------------------------------------------

    def get_user_role(
        self,
        user_id: str,
    ) -> str | None:
        ...

    # --------------------------------------------------------
    # Verify project ownership
    # --------------------------------------------------------

    def get_project_owner_id(
        self,
        project_id: str,
    ) -> str | None:
        ...

    # --------------------------------------------------------
    # Create conversation safely
    # --------------------------------------------------------

    def create_or_get(
        self,
        conversation: Conversation,
    ) -> Conversation:
        """
        Harus aman terhadap request bersamaan.

        Implementasi nanti menggunakan unique
        constraint database dan transaksi.
        """
        ...


# ============================================================
# 2. MESSAGE REPOSITORY CONTRACT
# ============================================================

class MessageRepository(Protocol):
    """
    Interface untuk mengakses pesan dan lampiran.
    """

    # --------------------------------------------------------
    # Get paginated message history
    # --------------------------------------------------------

    def list_for_conversation(
        self,
        conversation_id: str,
        *,
        limit: int,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[Message, ...]:
        """
        Keyset pagination berdasarkan:
        sent_at dan id.
        """
        ...

    # --------------------------------------------------------
    # Get single message
    # --------------------------------------------------------

    def get_by_id(
        self,
        message_id: str,
    ) -> Message | None:
        ...

    # --------------------------------------------------------
    # Retrieve attachment metadata
    # --------------------------------------------------------

    def list_attachments(
        self,
        message_ids: tuple[str, ...],
    ) -> tuple[MessageAttachment, ...]:
        ...

    # --------------------------------------------------------
    # Create message and attachments
    # --------------------------------------------------------

    def create_with_attachments(
        self,
        message: Message,
        attachments: tuple[MessageAttachment, ...],
    ) -> Message:
        """
        Insert pesan dan lampiran serta update
        conversations.last_message_at.

        Seluruhnya harus atomik.
        """
        ...

    # --------------------------------------------------------
    # Mark received messages as read
    # --------------------------------------------------------

    def mark_received_messages_read(
        self,
        conversation_id: str,
        recipient_user_id: str,
        read_at: datetime,
    ) -> int:
        """
        Hanya menandai pesan belum dibaca
        yang dikirim peserta lain.

        Harus menggunakan transaksi.
        """
        ...