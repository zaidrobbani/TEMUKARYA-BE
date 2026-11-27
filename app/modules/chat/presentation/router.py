import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import (
    File,
    Form,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    APIRouter,
    Depends,
    Query,
    status,
)

from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from app.core.exceptions import AppError, BadRequestError
from app.core.responses import ApiResponse, error_responses, success_response

from app.modules.chat.application.dto import (
    CreateConversationInput,
    DeleteMessagesInput,
    GetAttachmentFileInput,
    GetConversationInput,
    SendAttachmentMessageInput,
    ListConversationsInput,
    ListMessagesInput,
    MarkConversationReadInput,
    SendTextMessageInput,
)

from app.modules.chat.application.use_cases import (
    CreateOrGetConversation,
    DeleteMessages,
    GetConversation,
    GetMessageAttachmentFile,
    SendAttachmentMessage,
    ListUserConversations,
    ListConversationMessages,
    MarkConversationRead,
    SendTextMessage,
)

from app.modules.chat.domain.entities import ChatActor

from app.core.config import API_PREFIX
from app.modules.chat.domain.attachment_storage import ChatAttachmentStorage, thumbnail_key_of
from app.modules.chat.domain.entities import MessageDeleteScope, MessageType
from app.modules.chat.presentation.dependencies import (
    get_chat_attachment_storage,
    ChatDatabaseContext,
    NewMessageHook,
    get_authenticated_chat_actor,
    get_chat_database_context,
    get_new_message_hook,
)

from app.modules.chat.presentation.realtime import (
    CLOSE_NOT_FOUND,
    CLOSE_UNAUTHORIZED,
    ChatContextFactory,
    ChatHub,
    MessageNotifier,
    SocketAuthenticator,
    get_chat_context_factory,
    get_chat_hub,
    get_socket_authenticator,
    get_socket_message_notifier,
    token_from,
)
from app.modules.chat.presentation.schemas import (
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    DeleteMessagesRequest,
    DeleteMessagesResponse,
    MarkConversationReadResponse,
    MessageAttachmentResponse,
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
    notify: Annotated[
        NewMessageHook,
        Depends(get_new_message_hook),
    ],
    hub: Annotated[ChatHub, Depends(get_chat_hub)],
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

        notify(conversation_id, actor.user_id, result.message_text or "")

        db.session.commit()

        hub.broadcast_from_thread(conversation_id, _message_event(result))

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
        MessageWithAttachmentsResponse(
            message=MessageResponse.model_validate(item.message),
            attachments=[_attachment_response(conversation_id, a) for a in item.attachments],
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
# 5b. DELETE MESSAGES (hapus untuk saya / untuk semua orang)
# ============================================================

@router.post(
    "/{conversation_id}/messages/delete",
    response_model=ApiResponse[DeleteMessagesResponse],
    responses=error_responses(400, 401, 403, 404, 422),
    summary="Hapus banyak pesan sekaligus: untuk saya (ME) atau untuk semua orang (EVERYONE)",
)
def delete_messages(
    conversation_id: str,
    body: DeleteMessagesRequest,
    actor: Annotated[ChatActor, Depends(get_authenticated_chat_actor)],
    db: Annotated[ChatDatabaseContext, Depends(get_chat_database_context)],
    hub: Annotated[ChatHub, Depends(get_chat_hub)],
    storage: Annotated[ChatAttachmentStorage, Depends(get_chat_attachment_storage)],
):
    """
    Semua-atau-tidak-sama-sekali. EVERYONE di-push ke WebSocket sebagai
    `{"type":"message_deleted","conversation_id":…,"message_ids":[…],"deleted_at":…}`.
    """
    try:
        result = DeleteMessages(
            conversation_repository=db.conversations,
            message_repository=db.messages,
        ).execute(
            DeleteMessagesInput(
                conversation_id=conversation_id,
                actor=actor,
                message_ids=tuple(body.message_ids),
                scope=body.scope,
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    # File dibuang setelah commit: bila commit gagal, lampiran tetap utuh.
    for attachment in result.removed_attachments:
        _delete_stored_file(storage, attachment.storage_key)

    response = DeleteMessagesResponse.model_validate(result)
    if result.scope == MessageDeleteScope.EVERYONE:
        hub.broadcast_from_thread(conversation_id, _deleted_event(response))

    message = (
        "Pesan berhasil dihapus untuk semua orang"
        if result.scope == MessageDeleteScope.EVERYONE
        else "Pesan berhasil dihapus untuk saya"
    )
    return success_response(message, response)


def _delete_stored_file(storage: ChatAttachmentStorage, key: str) -> None:
    for item in (key, thumbnail_key_of(key)):
        if not item:
            continue
        try:
            storage.delete(item)
        except Exception:  # noqa: BLE001 - file yatim tidak boleh menggagalkan respons yang sudah di-commit
            pass


def _deleted_event(response: DeleteMessagesResponse) -> dict:
    data = response.model_dump(mode="json")
    return {
        "type": "message_deleted",
        "conversation_id": data["conversation_id"],
        "message_ids": data["message_ids"],
        "deleted_at": data["deleted_at"],
    }


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
    hub: Annotated[ChatHub, Depends(get_chat_hub)],
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

        hub.broadcast_from_thread(conversation_id, _read_event(conversation_id, actor, result.marked_count))

        return response

    except Exception:
        db.session.rollback()
        raise


# ============================================================
# 7. REAL-TIME (WEBSOCKET)
# ============================================================

def _attachment_response(conversation_id: str, attachment) -> MessageAttachmentResponse:
    base = f"{API_PREFIX}/conversations/{conversation_id}/attachments/{attachment.id}/file"
    response = MessageAttachmentResponse.model_validate(attachment)
    response.download_path = base
    response.thumbnail_path = f"{base}?thumbnail=true" if thumbnail_key_of(attachment.storage_key) else None
    return response


def _message_event(message, attachments=()) -> dict:
    return {
        "type": "message",
        "message": MessageResponse.model_validate(message).model_dump(mode="json"),
        "attachments": [
            _attachment_response(message.conversation_id, a).model_dump(mode="json") for a in attachments
        ],
    }


def _read_event(conversation_id: str, actor: ChatActor, marked_count: int) -> dict:
    return {
        "type": "read",
        "conversation_id": conversation_id,
        "reader_user_id": actor.user_id,
        "marked_count": marked_count,
        "read_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }


def _error_event(message: str, code: str | None = None) -> dict:
    event = {"type": "error", "message": message}
    if code:
        event["code"] = code
    return event


@router.websocket("/{conversation_id}/ws")
async def conversation_socket(
    websocket: WebSocket,
    conversation_id: str,
    hub: Annotated[ChatHub, Depends(get_chat_hub)],
    open_context: Annotated[ChatContextFactory, Depends(get_chat_context_factory)],
    authenticate: Annotated[SocketAuthenticator, Depends(get_socket_authenticator)],
    notify: Annotated[MessageNotifier, Depends(get_socket_message_notifier)],
):
    """
    Chat real-time satu percakapan. Token: header `Authorization: Bearer` atau query `?token=`.

    Client → server: `{"type":"message","text":"..."}`, `{"type":"read"}`, `{"type":"ping"}`.
    Server → client: `ready`, `message`, `read`, `message_deleted`, `pong`, `error`. Close 4401 = token tidak valid,
    4404 = percakapan tidak ada / bukan peserta.
    """
    token = token_from(websocket)
    try:
        actor = await run_in_threadpool(authenticate, token) if token else None
    except AppError:
        actor = None
    # Handshake diterima dulu: bila ditolak sebelum accept, uvicorn menjawab HTTP 403 dan kode close tidak sampai ke client.
    await websocket.accept()
    if actor is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED, reason="Token tidak valid, silakan login kembali")
        return

    def check_access() -> None:
        with open_context() as db:
            GetConversation(db.conversations).execute(GetConversationInput(conversation_id=conversation_id, actor=actor))

    try:
        await run_in_threadpool(check_access)
    except AppError:
        await websocket.close(code=CLOSE_NOT_FOUND, reason="Percakapan tidak ditemukan")
        return

    await hub.join(conversation_id, websocket)
    try:
        await websocket.send_json({"type": "ready", "conversation_id": conversation_id})
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                kind = data.get("type") if isinstance(data, dict) else None
            except ValueError:
                kind = None
            if kind == "ping":
                await websocket.send_json({"type": "pong"})
            elif kind == "message":
                text = data.get("text")
                if not isinstance(text, str):
                    await websocket.send_json(_error_event("Pesan harus berupa teks"))
                    continue
                try:
                    message = await run_in_threadpool(_send_message, open_context, notify, conversation_id, actor, text)
                except AppError as exc:
                    await websocket.send_json(_error_event(exc.message, exc.code))
                    continue
                await hub.broadcast(conversation_id, _message_event(message))
            elif kind == "read":
                try:
                    marked = await run_in_threadpool(_mark_read, open_context, conversation_id, actor)
                except AppError as exc:
                    await websocket.send_json(_error_event(exc.message, exc.code))
                    continue
                await hub.broadcast(conversation_id, _read_event(conversation_id, actor, marked))
            else:
                await websocket.send_json(_error_event("Tipe event tidak dikenal (gunakan message, read, atau ping)"))
    except WebSocketDisconnect:
        pass
    finally:
        await hub.leave(conversation_id, websocket)


def _send_message(
    open_context: ChatContextFactory, notify: MessageNotifier, conversation_id: str, actor: ChatActor, text: str
):
    # Sama seperti REST: simpan pesan + notifikasi dalam satu transaksi.
    with open_context() as db:
        try:
            result = SendTextMessage(
                conversation_repository=db.conversations,
                message_repository=db.messages,
            ).execute(SendTextMessageInput(conversation_id=conversation_id, actor=actor, message_text=text))
            notify(db.session, conversation_id, actor.user_id, result.message_text or "")
            db.session.commit()
            return result
        except Exception:
            db.session.rollback()
            raise


def _mark_read(open_context: ChatContextFactory, conversation_id: str, actor: ChatActor) -> int:
    with open_context() as db:
        try:
            result = MarkConversationRead(
                conversation_repository=db.conversations,
                message_repository=db.messages,
            ).execute(MarkConversationReadInput(conversation_id=conversation_id, actor=actor))
            db.session.commit()
            return result.marked_count
        except Exception:
            db.session.rollback()
            raise



# ============================================================
# 8. LAMPIRAN (FOTO / DOKUMEN)
# ============================================================

_IMAGE_SIGNATURES = (b"\xff\xd8", b"\x89PNG\r\n\x1a\n")


def _looks_like_image(upload: UploadFile) -> bool:
    head = upload.file.read(12)
    upload.file.seek(0)
    return head.startswith(_IMAGE_SIGNATURES) or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")


@router.post(
    "/{conversation_id}/attachments",
    response_model=ApiResponse[MessageWithAttachmentsResponse],
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 403, 404, 413, 415, 422, 503),
    summary="Kirim foto (dikompres ke WebP + thumbnail) atau dokumen, dengan caption opsional",
)
def send_attachment_message(
    conversation_id: str,
    actor: Annotated[ChatActor, Depends(get_authenticated_chat_actor)],
    db: Annotated[ChatDatabaseContext, Depends(get_chat_database_context)],
    notify: Annotated[NewMessageHook, Depends(get_new_message_hook)],
    hub: Annotated[ChatHub, Depends(get_chat_hub)],
    storage: Annotated[ChatAttachmentStorage, Depends(get_chat_attachment_storage)],
    file: UploadFile = File(..., description="Foto JPG/PNG/WebP (maks 10 MB) atau dokumen PDF/Office/TXT/CSV/ZIP (maks 10 MB)"),
    caption: str | None = Form(None, description="Keterangan opsional"),
):
    try:
        message, attachments = SendAttachmentMessage(
            conversation_repository=db.conversations,
            message_repository=db.messages,
            storage=storage,
        ).execute(
            SendAttachmentMessageInput(
                conversation_id=conversation_id,
                actor=actor,
                file_name=file.filename or "",
                source=file.file,
                is_image=_looks_like_image(file),
                caption=caption,
            )
        )
        preview = message.message_text or (
            "📷 Foto" if message.message_type == MessageType.IMAGE else f"📄 {attachments[0].original_file_name}"
        )
        notify(conversation_id, actor.user_id, preview)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    hub.broadcast_from_thread(conversation_id, _message_event(message, attachments))
    return success_response(
        "Lampiran berhasil dikirim",
        MessageWithAttachmentsResponse(
            message=MessageResponse.model_validate(message),
            attachments=[_attachment_response(conversation_id, a) for a in attachments],
        ),
    )


@router.get(
    "/{conversation_id}/attachments/{attachment_id}/file",
    response_class=StreamingResponse,
    responses=error_responses(401, 404, 503),
    summary="Unduh lampiran chat (biner). thumbnail=true untuk pratinjau foto",
)
def download_attachment(
    conversation_id: str,
    attachment_id: str,
    actor: Annotated[ChatActor, Depends(get_authenticated_chat_actor)],
    db: Annotated[ChatDatabaseContext, Depends(get_chat_database_context)],
    storage: Annotated[ChatAttachmentStorage, Depends(get_chat_attachment_storage)],
    thumbnail: bool = False,
):
    attachment, mime, stream = GetMessageAttachmentFile(
        conversation_repository=db.conversations,
        message_repository=db.messages,
        storage=storage,
    ).execute(
        GetAttachmentFileInput(
            conversation_id=conversation_id,
            attachment_id=attachment_id,
            actor=actor,
            thumbnail=thumbnail,
        )
    )
    safe_name = "".join(c if c.isascii() and c not in '"\\' else "_" for c in attachment.original_file_name)
    return StreamingResponse(
        iter(lambda: stream.read(64 * 1024), b""),
        media_type=mime,
        # File lampiran tidak pernah berubah setelah dikirim, aman di-cache client.
        headers={
            "Cache-Control": "private, max-age=604800, immutable",
            "Content-Disposition": f'inline; filename="{safe_name}"',
        },
        background=BackgroundTask(stream.close),
    )
