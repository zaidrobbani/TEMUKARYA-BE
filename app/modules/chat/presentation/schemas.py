from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.core.responses import UtcDateTime

from app.modules.chat.domain.entities import (
    MessageDeleteScope,
    MessageType,
)


class ChatResponseBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )


class CreateConversationRequest(BaseModel):
    counterpart_user_id: str = Field(
        min_length=1,
        max_length=36,
    )

    project_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=36,
    )


class ConversationResponse(ChatResponseBase):
    id: str

    umkm_id: str
    freelancer_id: str

    project_id: str | None

    last_message_at: UtcDateTime | None

    created_at: UtcDateTime
    updated_at: UtcDateTime


class ConversationListResponse(ChatResponseBase):
    items: list[ConversationResponse]

    limit: int
    offset: int


class SendTextMessageRequest(BaseModel):
    message_text: str = Field(
        min_length=1,
        max_length=4000,
    )


class MessageResponse(ChatResponseBase):
    id: str

    conversation_id: str
    sender_user_id: str

    message_text: str | None
    message_type: MessageType

    sent_at: UtcDateTime
    created_at: UtcDateTime

    read_at: UtcDateTime | None

    deleted_at: UtcDateTime | None = None


class MessageAttachmentResponse(ChatResponseBase):
    id: str
    message_id: str

    original_file_name: str
    mime_type: str
    file_size_bytes: int

    uploaded_at: UtcDateTime

    download_path: str | None = None
    thumbnail_path: str | None = None


class MessageWithAttachmentsResponse(
    ChatResponseBase
):
    message: MessageResponse

    attachments: list[
        MessageAttachmentResponse
    ]


class MessageCursorResponse(ChatResponseBase):
    sent_at: UtcDateTime
    message_id: str


class MessagePageResponse(BaseModel):
    conversation_id: str

    items: list[
        MessageWithAttachmentsResponse
    ]

    has_more: bool

    next_before: (
        MessageCursorResponse | None
    ) = None


class MarkConversationReadResponse(
    ChatResponseBase
):
    conversation_id: str

    marked_count: int


class DeleteMessagesRequest(BaseModel):
    message_ids: list[str] = Field(min_length=1, max_length=100)
    scope: MessageDeleteScope = Field(
        description="ME = hapus untuk saya, EVERYONE = hapus untuk semua orang (pesan sendiri, maks 48 jam)",
    )


class DeleteMessagesResponse(ChatResponseBase):
    conversation_id: str
    scope: MessageDeleteScope
    message_ids: list[str]
    deleted_at: UtcDateTime
