from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


# 1. MESSAGE TYPE

class MessageType(StrEnum):
    """
    Jenis pesan yang didukung TEMUKARYA.
    """

    TEXT = "TEXT"
    IMAGE = "IMAGE"
    FILE = "FILE"


# 2. CHAT ACTOR

@dataclass(frozen=True, slots=True)
class ChatActor:
    """
    Representasi pengguna yang sudah login.

    Identitas harus berasal dari autentikasi
    yang telah diverifikasi, bukan request client.
    """

    user_id: str
    role: str


# 3. CONVERSATION ENTITY

@dataclass(frozen=True, slots=True)
class Conversation:
    """
    Representasi percakapan UMKM dan Freelancer.

    project_id = None:
        Percakapan umum.

    project_id != None:
        Percakapan untuk project tertentu.
    """

    id: str
    umkm_id: str
    freelancer_id: str

    project_id: str | None

    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


# 4. MESSAGE ENTITY

@dataclass(frozen=True, slots=True)
class Message:
    """
    Representasi satu pesan dalam percakapan.
    """

    id: str
    conversation_id: str
    sender_user_id: str

    message_text: str | None
    message_type: MessageType

    sent_at: datetime
    created_at: datetime

    read_at: datetime | None = None


# 5. MESSAGE ATTACHMENT ENTITY

@dataclass(frozen=True, slots=True)
class MessageAttachment:
    """
    Metadata file yang dilampirkan pada pesan.

    File fisik disimpan melalui Storage Module.
    Database hanya menyimpan metadata.
    """

    id: str
    message_id: str

    original_file_name: str
    storage_key: str
    mime_type: str
    file_size_bytes: int

    uploaded_at: datetime