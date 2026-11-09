from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.core.responses import UtcDateTime

from app.modules.chat.domain.entities import (
    MessageType,
)


# ============================================================
# 1. BASE RESPONSE SCHEMA
# ============================================================

class ChatResponseBase(BaseModel):
    """
    Base schema untuk response Chat Module.

    Mendukung konversi dari Domain Dataclass
    menjadi Pydantic Response Model.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )


# ============================================================
# 2. CREATE CONVERSATION REQUEST
# ============================================================

class CreateConversationRequest(BaseModel):
    """
    Request untuk memulai percakapan.

    Actor tidak boleh dikirim oleh client.
    Actor diperoleh dari JWT Authentication.
    """

    counterpart_user_id: str = Field(
        min_length=1,
        max_length=36,
    )

    project_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=36,
    )


# ============================================================
# 3. CONVERSATION RESPONSE
# ============================================================

class ConversationResponse(ChatResponseBase):
    """
    Detail satu percakapan.
    """

    id: str

    umkm_id: str
    freelancer_id: str

    project_id: str | None

    last_message_at: UtcDateTime | None

    created_at: UtcDateTime
    updated_at: UtcDateTime


# ============================================================
# 4. CONVERSATION LIST RESPONSE
# ============================================================

class ConversationListResponse(ChatResponseBase):
    """
    Daftar percakapan pengguna.

    FIX IMPORT ERROR:
    Class ini dibutuhkan oleh router.py.
    """

    items: list[ConversationResponse]

    limit: int
    offset: int


# ============================================================
# 5. SEND TEXT MESSAGE REQUEST
# ============================================================

class SendTextMessageRequest(BaseModel):
    """
    Request pengiriman pesan teks.

    sender_user_id tidak diterima dari body.
    """

    message_text: str = Field(
        min_length=1,
        max_length=4000,
    )


# ============================================================
# 6. MESSAGE RESPONSE
# ============================================================

class MessageResponse(ChatResponseBase):
    """
    Detail pesan yang dikirim atau diterima.
    """

    id: str

    conversation_id: str
    sender_user_id: str

    message_text: str | None
    message_type: MessageType

    sent_at: UtcDateTime
    created_at: UtcDateTime

    read_at: UtcDateTime | None


# ============================================================
# 7. MESSAGE ATTACHMENT RESPONSE
# ============================================================

class MessageAttachmentResponse(ChatResponseBase):
    """
    Metadata lampiran pesan.

    storage_key tidak diekspos kepada client.
    """

    id: str
    message_id: str

    original_file_name: str
    mime_type: str
    file_size_bytes: int

    uploaded_at: UtcDateTime


# ============================================================
# 8. MESSAGE WITH ATTACHMENTS RESPONSE
# ============================================================

class MessageWithAttachmentsResponse(
    ChatResponseBase
):
    """
    Satu pesan dan daftar lampirannya.
    """

    message: MessageResponse

    attachments: list[
        MessageAttachmentResponse
    ]


# ============================================================
# 9. MESSAGE PAGINATION CURSOR
# ============================================================

class MessageCursorResponse(ChatResponseBase):
    """
    Cursor untuk keyset pagination.

    Menggunakan sent_at dan message_id.
    """

    sent_at: UtcDateTime
    message_id: str


# ============================================================
# 10. MESSAGE PAGE RESPONSE
# ============================================================

class MessagePageResponse(BaseModel):
    """
    Halaman riwayat pesan.
    """

    conversation_id: str

    items: list[
        MessageWithAttachmentsResponse
    ]

    has_more: bool

    next_before: (
        MessageCursorResponse | None
    ) = None


# ============================================================
# 11. MARK CONVERSATION READ RESPONSE
# ============================================================

class MarkConversationReadResponse(
    ChatResponseBase
):
    """
    Hasil penandaan pesan sebagai dibaca.
    """

    conversation_id: str

    marked_count: int