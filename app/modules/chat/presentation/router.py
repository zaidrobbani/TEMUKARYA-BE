from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
    status,
)

from app.core.exceptions import BadRequestError
from app.core.responses import ApiResponse, error_responses, success_response

from app.modules.chat.application.dto import (
    CreateConversationInput,
    GetConversationInput,
    ListConversationsInput,
    ListMessagesInput,
    MarkConversationReadInput,
    SendTextMessageInput,
)

from app.modules.chat.application.use_cases import (
    CreateOrGetConversation,
    GetConversation,
    ListUserConversations,
    ListConversationMessages,
    MarkConversationRead,
    SendTextMessage,
)

from app.modules.chat.domain.entities import ChatActor

from app.modules.chat.presentation.dependencies import (
    ChatDatabaseContext,
    get_authenticated_chat_actor,
    get_chat_database_context,
)

from app.modules.chat.presentation.schemas import (
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    MarkConversationReadResponse,
    MessageCursorResponse,
    MessagePageResponse,
    MessageResponse,
    MessageWithAttachmentsResponse,
    SendTextMessageRequest,
)


# ============================================================
# ROUTER CONFIGURATION
# ============================================================

router = APIRouter(
    prefix="/conversations",
    tags=["chat"],
)


# ============================================================
# 1. CREATE OR GET CONVERSATION
# ============================================================

@router.post(
    "",
    response_model=ApiResponse[ConversationResponse],
    status_code=status.HTTP_200_OK,
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
def create_or_get_conversation(
    body: CreateConversationRequest,
    actor: Annotated[
        ChatActor,
        Depends(get_authenticated_chat_actor),
    ],
    db: Annotated[
        ChatDatabaseContext,
        Depends(get_chat_database_context),
    ],
):
    """
    Membuat percakapan baru atau mengambil
    percakapan yang sudah ada.

    Mengembalikan 200 untuk keduanya.
    """

    try:
        use_case = CreateOrGetConversation(
            db.conversations
        )

        result = use_case.execute(
            CreateConversationInput(
                actor=actor,
                counterpart_user_id=(
                    body.counterpart_user_id
                ),
                project_id=body.project_id,
            )
        )

        response = success_response(
            "Percakapan berhasil dibuka",
            ConversationResponse.model_validate(result),
        )

        db.session.commit()

        return response

    except Exception:
        db.session.rollback()
        raise


# ============================================================
# 2. LIST MY CONVERSATIONS
# ============================================================

@router.get(
    "",
    response_model=ApiResponse[ConversationListResponse],
    responses=error_responses(400, 401, 403, 422),
)
def list_my_conversations(
    actor: Annotated[
        ChatActor,
        Depends(get_authenticated_chat_actor),
    ],
    db: Annotated[
        ChatDatabaseContext,
        Depends(get_chat_database_context),
    ],
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
):
    """
    Hanya menampilkan conversation
    milik pengguna yang login.
    """

    use_case = ListUserConversations(
        db.conversations
    )

    result = use_case.execute(
        ListConversationsInput(
            actor=actor,
            limit=limit,
            offset=offset,
        )
    )

    return success_response(
        "Daftar percakapan berhasil diambil",
        ConversationListResponse.model_validate(result),
    )


# ============================================================
# 3. GET CONVERSATION DETAIL
# ============================================================

@router.get(
    "/{conversation_id}",
    response_model=ApiResponse[ConversationResponse],
    responses=error_responses(400, 401, 403, 404),
)
def get_conversation_detail(
    conversation_id: str,
    actor: Annotated[
        ChatActor,
        Depends(get_authenticated_chat_actor),
    ],
    db: Annotated[
        ChatDatabaseContext,
        Depends(get_chat_database_context),
    ],
):
    """
    Mengambil detail chat berdasarkan ID.

    Hanya dua peserta conversation
    yang boleh melihat isinya.
    """

    use_case = GetConversation(
        db.conversations
    )

    result = use_case.execute(
        GetConversationInput(
            conversation_id=conversation_id,
            actor=actor,
        )
    )

    return success_response(
        "Detail percakapan berhasil diambil",
        ConversationResponse.model_validate(result),
    )


# ============================================================
# 4. SEND TEXT MESSAGE
# ============================================================

@router.post(
    "/{conversation_id}/messages",
    response_model=ApiResponse[MessageResponse],
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 403, 404, 422),
)
def send_text_message(
    conversation_id: str,
    body: SendTextMessageRequest,
    actor: Annotated[
        ChatActor,
        Depends(get_authenticated_chat_actor),
    ],
    db: Annotated[
        ChatDatabaseContext,
        Depends(get_chat_database_context),
    ],
):
    """
    Mengirim pesan teks.

    Sender ID tidak diterima dari body.
    Identitas sender berasal dari JWT.

    INSERT dan UPDATE last_message_at
    harus di-commit bersama.
    """

    try:
        use_case = SendTextMessage(
            conversation_repository=db.conversations,
            message_repository=db.messages,
        )

        result = use_case.execute(
            SendTextMessageInput(
                conversation_id=conversation_id,
                actor=actor,
                message_text=body.message_text,
            )
        )

        response = success_response(
            "Pesan berhasil dikirim",
            MessageResponse.model_validate(result),
        )

        db.session.commit()

        return response

    except Exception:
        db.session.rollback()
        raise


# ============================================================
# 5. GET MESSAGE HISTORY
# ============================================================

@router.get(
    "/{conversation_id}/messages",
    response_model=ApiResponse[MessagePageResponse],
    responses=error_responses(400, 401, 403, 404, 422),
)
def get_message_history(
    conversation_id: str,
    actor: Annotated[
        ChatActor,
        Depends(get_authenticated_chat_actor),
    ],
    db: Annotated[
        ChatDatabaseContext,
        Depends(get_chat_database_context),
    ],
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    before_at: datetime | None = Query(
        default=None,
    ),
    before_id: str | None = Query(
        default=None,
        max_length=36,
    ),
):
    """
    Riwayat pesan diurutkan:
    sent_at DESC, id DESC.

    Pagination memakai dua parameter:
    before_at dan before_id.
    """

    if (before_at is None) != (before_id is None):
        raise BadRequestError(
            "before_at dan before_id harus "
            "dikirim bersama"
        )

    cursor = None

    if before_at is not None:
        if (
            before_at.tzinfo is None
            or before_at.utcoffset() is None
        ):
            raise BadRequestError(
                "before_at harus menyertakan timezone"
            )

        if not before_id or not before_id.strip():
            raise BadRequestError(
                "before_id tidak boleh kosong"
            )

        cursor = (
            before_at,
            before_id,
        )

    use_case = ListConversationMessages(
        conversation_repository=db.conversations,
        message_repository=db.messages,
    )

    result = use_case.execute(
        ListMessagesInput(
            conversation_id=conversation_id,
            actor=actor,
            limit=limit,
            before=cursor,
        )
    )

    # Convert Domain DTO into safe response.
    # storage_key sengaja tidak diekspos.
    items = [
        MessageWithAttachmentsResponse.model_validate(
            item
        )
        for item in result.items
    ]

    next_cursor = None

    if result.next_before is not None:
        next_cursor = MessageCursorResponse(
            sent_at=result.next_before[0],
            message_id=result.next_before[1],
        )

    return success_response(
        "Riwayat pesan berhasil diambil",
        MessagePageResponse(
            conversation_id=result.conversation_id,
            items=items,
            has_more=result.has_more,
            next_before=next_cursor,
        ),
    )


# ============================================================
# 6. MARK CONVERSATION READ
# ============================================================

@router.patch(
    "/{conversation_id}/read",
    response_model=ApiResponse[MarkConversationReadResponse],
    responses=error_responses(400, 401, 403, 404, 409),
)
def mark_conversation_read(
    conversation_id: str,
    actor: Annotated[
        ChatActor,
        Depends(get_authenticated_chat_actor),
    ],
    db: Annotated[
        ChatDatabaseContext,
        Depends(get_chat_database_context),
    ],
):
    """
    Menandai pesan masuk yang belum dibaca.

    Mengabaikan pesan milik pengirim sendiri.

    Operasi berulang harus idempotent.
    """

    try:
        use_case = MarkConversationRead(
            conversation_repository=db.conversations,
            message_repository=db.messages,
        )

        result = use_case.execute(
            MarkConversationReadInput(
                conversation_id=conversation_id,
                actor=actor,
            )
        )

        response = success_response(
            "Percakapan berhasil ditandai sudah dibaca",
            MarkConversationReadResponse.model_validate(result),
        )

        db.session.commit()

        return response

    except Exception:
        db.session.rollback()
        raise