from datetime import datetime
from typing import Protocol

from app.modules.chat.domain.entities import (
    Conversation,
    Message,
    MessageAttachment,
)


class ConversationRepository(Protocol):
    def find_by_participants(
        self,
        umkm_id: str,
        freelancer_id: str,
        project_id: str | None,
    ) -> Conversation | None:
        ...

    def get_by_id(
        self,
        conversation_id: str,
    ) -> Conversation | None:
        ...

    def list_for_user(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[Conversation, ...]:
        ...

    def get_user_role(
        self,
        user_id: str,
    ) -> str | None:
        ...

    def get_project_owner_id(
        self,
        project_id: str,
    ) -> str | None:
        ...

    def create_or_get(
        self,
        conversation: Conversation,
    ) -> Conversation:
        ...


class MessageRepository(Protocol):
    def list_for_conversation(
        self,
        conversation_id: str,
        *,
        limit: int,
        before: tuple[datetime, str] | None = None,
        viewer_user_id: str | None = None,
    ) -> tuple[Message, ...]:
        ...

    def get_by_id(
        self,
        message_id: str,
    ) -> Message | None:
        ...

    def list_attachments(
        self,
        message_ids: tuple[str, ...],
    ) -> tuple[MessageAttachment, ...]:
        ...

    def get_attachment(
        self,
        attachment_id: str,
    ) -> tuple[MessageAttachment, str] | None:
        ...

    def create_with_attachments(
        self,
        message: Message,
        attachments: tuple[MessageAttachment, ...],
    ) -> Message:
        ...

    def mark_received_messages_read(
        self,
        conversation_id: str,
        recipient_user_id: str,
        read_at: datetime,
    ) -> int:
        ...

    def list_by_ids(
        self,
        conversation_id: str,
        message_ids: tuple[str, ...],
    ) -> tuple[Message, ...]:
        ...

    def delete_for_everyone(
        self,
        message_ids: tuple[str, ...],
        deleted_at: datetime,
    ) -> tuple[MessageAttachment, ...]:
        ...

    def hide_for_user(
        self,
        message_ids: tuple[str, ...],
        user_id: str,
        hidden_at: datetime,
    ) -> None:
        ...
