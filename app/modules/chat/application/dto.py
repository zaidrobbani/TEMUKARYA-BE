from dataclasses import dataclass
from datetime import datetime

from app.modules.chat.domain.entities import (
    ChatActor,
    Conversation,
    Message,
    MessageAttachment,
)


# ============================================================
# 1. CREATE OR GET CONVERSATION
# ============================================================

@dataclass(frozen=True, slots=True)
class CreateConversationInput:
    """
    Memulai chat dengan pengguna lain.

    Identitas UMKM dan Freelancer ditentukan
    dari actor dan role pengguna tujuan.
    """

    actor: ChatActor
    counterpart_user_id: str
    project_id: str | None = None


# ============================================================
# 2. GET CONVERSATION
# ============================================================

@dataclass(frozen=True, slots=True)
class GetConversationInput:
    conversation_id: str
    actor: ChatActor


# ============================================================
# 3. LIST CONVERSATIONS
# ============================================================

@dataclass(frozen=True, slots=True)
class ListConversationsInput:
    actor: ChatActor
    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class ConversationListResult:
    items: tuple[Conversation, ...]
    limit: int
    offset: int


# ============================================================
# 4. SEND TEXT MESSAGE
# ============================================================

@dataclass(frozen=True, slots=True)
class SendTextMessageInput:
    conversation_id: str
    actor: ChatActor
    message_text: str


# ============================================================
# 5. LIST MESSAGES
# ============================================================

@dataclass(frozen=True, slots=True)
class ListMessagesInput:
    conversation_id: str
    actor: ChatActor

    limit: int = 20

    # Keyset cursor: (sent_at, message_id)
    before: tuple[datetime, str] | None = None


@dataclass(frozen=True, slots=True)
class MessageWithAttachments:
    message: Message
    attachments: tuple[MessageAttachment, ...]


@dataclass(frozen=True, slots=True)
class MessagePage:
    conversation_id: str
    items: tuple[MessageWithAttachments, ...]

    has_more: bool

    next_before: tuple[datetime, str] | None


# ============================================================
# 6. MARK CONVERSATION AS READ
# ============================================================

@dataclass(frozen=True, slots=True)
class MarkConversationReadInput:
    conversation_id: str
    actor: ChatActor


@dataclass(frozen=True, slots=True)
class MarkConversationReadResult:
    conversation_id: str
    marked_count: int