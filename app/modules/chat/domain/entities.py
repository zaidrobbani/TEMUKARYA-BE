from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MessageType(StrEnum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    FILE = "FILE"


class MessageDeleteScope(StrEnum):
    ME = "ME"
    EVERYONE = "EVERYONE"


@dataclass(frozen=True, slots=True)
class ChatActor:
    user_id: str
    role: str


@dataclass(frozen=True, slots=True)
class Conversation:
    id: str
    umkm_id: str
    freelancer_id: str

    project_id: str | None

    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    conversation_id: str
    sender_user_id: str

    message_text: str | None
    message_type: MessageType

    sent_at: datetime
    created_at: datetime

    read_at: datetime | None = None

    deleted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MessageAttachment:
    id: str
    message_id: str

    original_file_name: str
    storage_key: str
    mime_type: str
    file_size_bytes: int

    uploaded_at: datetime
