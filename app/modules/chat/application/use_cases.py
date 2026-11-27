from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import BinaryIO
from uuid import uuid4

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

from app.modules.chat.application.dto import (
    CreateConversationInput,
    GetConversationInput,
    ListConversationsInput,
    ConversationListResult,
    SendTextMessageInput,
    ListMessagesInput,
    MessageWithAttachments,
    MessagePage,
    MarkConversationReadInput,
    MarkConversationReadResult,
    SendAttachmentMessageInput,
    GetAttachmentFileInput,
    DeleteMessagesInput,
    DeleteMessagesResult,
)

from app.modules.chat.domain.entities import (
    ChatActor,
    Conversation,
    Message,
    MessageAttachment,
    MessageDeleteScope,
    MessageType,
)

from app.modules.chat.domain.repositories import (
    ConversationRepository,
    MessageRepository,
)

from app.modules.chat.domain.conversation_rules import (
    require_chat_actor,
    require_conversation_access,
    require_conversation_initiator,
    validate_chat_id,
)

from app.modules.chat.domain.attachment_storage import (
    ChatAttachmentStorage,
    ChatFileNotFoundError,
    thumbnail_key_of,
)
from app.modules.chat.domain.message_rules import (
    normalize_message_text,
    require_attachment_belongs_to_message,
    validate_message_payload,
)

from app.modules.users.domain.entities import UserRole


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_id(
    value: str,
    field_name: str,
) -> str:
    try:
        return validate_chat_id(
            value,
            field_name,
        )
    except ValueError as exc:
        raise BadRequestError(
            str(exc)
        ) from exc


def _validate_actor(
    actor: ChatActor,
) -> None:
    try:
        require_chat_actor(actor)
    except (ValueError, PermissionError) as exc:
        raise ForbiddenError(
            "Identitas atau role tidak diizinkan"
        ) from exc

    if actor.user_id != actor.user_id.strip():
        raise ForbiddenError(
            "Identitas pengguna tidak valid"
        )


def _require_access(
    conversation: Conversation,
    actor: ChatActor,
) -> None:
    try:
        require_conversation_access(
            conversation,
            actor,
        )
    except PermissionError as exc:
        raise NotFoundError(
            "Percakapan tidak ditemukan"
        ) from exc
    except ValueError as exc:
        raise ConflictError(
            "Data peserta percakapan tidak valid"
        ) from exc


def _validate_page(
    limit: int,
    offset: int | None = None,
) -> None:
    if (
        type(limit) is not int
        or not (1 <= limit <= 100)
    ):
        raise BadRequestError(
            "Limit harus antara 1 dan 100"
        )

    if offset is not None:
        if (
            type(offset) is not int
            or offset < 0
        ):
            raise BadRequestError(
                "Offset harus bilangan bulat >= 0"
            )


class CreateOrGetConversation:
    def __init__(
        self,
        repository: ConversationRepository,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self.repository = repository
        self.clock = clock

    def execute(
        self,
        data: CreateConversationInput,
    ) -> Conversation:
        actor = data.actor
        _validate_actor(actor)

        counterpart_id = _validate_id(
            data.counterpart_user_id,
            "Counterpart ID",
        )

        if counterpart_id == actor.user_id:
            raise BadRequestError(
                "Tidak dapat chat dengan akun sendiri"
            )

        counterpart_role = (
            self.repository.get_user_role(
                counterpart_id
            )
        )

        expected_role = (
            UserRole.FREELANCER
            if actor.role == UserRole.UMKM
            else UserRole.UMKM
        )

        if counterpart_role != expected_role:
            raise NotFoundError(
                "Pengguna tujuan tidak ditemukan"
            )

        if actor.role == UserRole.UMKM:
            umkm_id = actor.user_id
            freelancer_id = counterpart_id
        else:
            umkm_id = counterpart_id
            freelancer_id = actor.user_id

        project_id = (
            _validate_id(
                data.project_id,
                "Project ID",
            )
            if data.project_id is not None
            else None
        )

        try:
            require_conversation_initiator(
                actor=actor,
                umkm_id=umkm_id,
                freelancer_id=freelancer_id,
                project_id=project_id,
            )
        except ValueError as exc:
            raise BadRequestError(
                str(exc)
            ) from exc
        except PermissionError as exc:
            raise ForbiddenError(
                "Tidak boleh memulai percakapan"
            ) from exc

        if project_id is not None:
            project_owner_id = (
                self.repository.get_project_owner_id(
                    project_id
                )
            )

            if project_owner_id != umkm_id:
                raise NotFoundError(
                    "Project tidak ditemukan"
                )

        existing = (
            self.repository.find_by_participants(
                umkm_id=umkm_id,
                freelancer_id=freelancer_id,
                project_id=project_id,
            )
        )

        if existing is not None:
            self._verify_result(
                existing,
                umkm_id,
                freelancer_id,
                project_id,
            )

            return existing

        now = self.clock()

        conversation = Conversation(
            id=str(uuid4()),
            umkm_id=umkm_id,
            freelancer_id=freelancer_id,
            project_id=project_id,
            last_message_at=None,
            created_at=now,
            updated_at=now,
        )

        created = self.repository.create_or_get(
            conversation
        )

        self._verify_result(
            created,
            umkm_id,
            freelancer_id,
            project_id,
        )

        return created

    @staticmethod
    def _verify_result(
        conversation: Conversation,
        umkm_id: str,
        freelancer_id: str,
        project_id: str | None,
    ) -> None:
        if (
            not isinstance(conversation, Conversation)
            or conversation.umkm_id != umkm_id
            or conversation.freelancer_id != freelancer_id
            or conversation.project_id != project_id
        ):
            raise ConflictError(
                "Data percakapan tidak konsisten"
            )


class GetConversation:
    def __init__(
        self,
        repository: ConversationRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: GetConversationInput,
    ) -> Conversation:
        _validate_actor(data.actor)

        conversation_id = _validate_id(
            data.conversation_id,
            "Conversation ID",
        )

        conversation = self.repository.get_by_id(
            conversation_id
        )

        if conversation is None:
            raise NotFoundError(
                "Percakapan tidak ditemukan"
            )

        _require_access(
            conversation,
            data.actor,
        )

        return conversation


class ListUserConversations:
    def __init__(
        self,
        repository: ConversationRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: ListConversationsInput,
    ) -> ConversationListResult:
        _validate_actor(data.actor)

        _validate_page(
            data.limit,
            data.offset,
        )

        items = tuple(
            self.repository.list_for_user(
                data.actor.user_id,
                limit=data.limit,
                offset=data.offset,
            )
        )

        if len(items) > data.limit:
            raise ConflictError(
                "Repository mengembalikan terlalu "
                "banyak percakapan"
            )

        for conversation in items:
            try:
                require_conversation_access(
                    conversation,
                    data.actor,
                )
            except (PermissionError, ValueError) as exc:
                raise ConflictError(
                    "Repository mengembalikan "
                    "percakapan tidak sah"
                ) from exc

        return ConversationListResult(
            items=items,
            limit=data.limit,
            offset=data.offset,
        )


class SendTextMessage:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self.conversation_repository = (
            conversation_repository
        )

        self.message_repository = (
            message_repository
        )

        self.clock = clock

        self.get_conversation = GetConversation(
            conversation_repository
        )

    def execute(
        self,
        data: SendTextMessageInput,
    ) -> Message:
        conversation = (
            self.get_conversation.execute(
                GetConversationInput(
                    conversation_id=data.conversation_id,
                    actor=data.actor,
                )
            )
        )

        try:
            message_text = validate_message_payload(
                message_type=MessageType.TEXT,
                message_text=data.message_text,
                attachments=(),
            )
        except ValueError as exc:
            raise BadRequestError(
                str(exc)
            ) from exc

        now = self.clock()

        message = Message(
            id=str(uuid4()),
            conversation_id=conversation.id,
            sender_user_id=data.actor.user_id,
            message_text=message_text,
            message_type=MessageType.TEXT,
            sent_at=now,
            created_at=now,
            read_at=None,
        )

        saved = (
            self.message_repository.create_with_attachments(
                message=message,
                attachments=(),
            )
        )

        if (
            not isinstance(saved, Message)
            or saved.id != message.id
            or saved.conversation_id != conversation.id
            or saved.sender_user_id != data.actor.user_id
            or saved.message_type != MessageType.TEXT
            or saved.message_text != message_text
        ):
            raise ConflictError(
                "Pesan tersimpan tidak konsisten"
            )

        return saved


class ListConversationMessages:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
    ):
        self.conversation_repository = (
            conversation_repository
        )

        self.message_repository = (
            message_repository
        )

        self.get_conversation = GetConversation(
            conversation_repository
        )

    def execute(
        self,
        data: ListMessagesInput,
    ) -> MessagePage:
        conversation = (
            self.get_conversation.execute(
                GetConversationInput(
                    conversation_id=data.conversation_id,
                    actor=data.actor,
                )
            )
        )

        _validate_page(data.limit)

        if data.before is not None:
            if (
                not isinstance(data.before, tuple)
                or len(data.before) != 2
                or not isinstance(
                    data.before[0],
                    datetime,
                )
            ):
                raise BadRequestError(
                    "Cursor tidak valid"
                )

            _validate_id(
                data.before[1],
                "Cursor message ID",
            )

        fetched = tuple(
            self.message_repository.list_for_conversation(
                conversation.id,
                limit=data.limit + 1,
                before=data.before,
                viewer_user_id=data.actor.user_id,
            )
        )

        if len(fetched) > data.limit + 1:
            raise ConflictError(
                "Repository mengembalikan "
                "terlalu banyak pesan"
            )

        has_more = len(fetched) > data.limit

        messages = fetched[:data.limit]

        allowed_senders = {
            conversation.umkm_id,
            conversation.freelancer_id,
        }

        for message in messages:
            if (
                not isinstance(message, Message)
                or message.conversation_id
                != conversation.id
                or message.sender_user_id
                not in allowed_senders
            ):
                raise ConflictError(
                    "Data pesan tidak konsisten"
                )

        message_ids = tuple(
            item.id
            for item in messages
        )

        attachments = (
            tuple(
                self.message_repository.list_attachments(
                    message_ids
                )
            )
            if message_ids
            else ()
        )

        grouped = {
            message_id: []
            for message_id in message_ids
        }

        message_map = {
            item.id: item
            for item in messages
        }

        for attachment in attachments:
            message = message_map.get(
                attachment.message_id
            )

            if message is None:
                raise ConflictError(
                    "Lampiran bukan milik halaman pesan"
                )

            try:
                require_attachment_belongs_to_message(
                    attachment,
                    message,
                )
            except ValueError as exc:
                raise ConflictError(
                    "Metadata lampiran tidak valid"
                ) from exc

            grouped[message.id].append(
                attachment
            )

        items = tuple(
            MessageWithAttachments(
                message=message,
                attachments=tuple(
                    grouped[message.id]
                ),
            )
            for message in messages
        )

        next_before = None

        if has_more and messages:
            last = messages[-1]

            next_before = (
                last.sent_at,
                last.id,
            )

        return MessagePage(
            conversation_id=conversation.id,
            items=items,
            has_more=has_more,
            next_before=next_before,
        )


class MarkConversationRead:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self.conversation_repository = (
            conversation_repository
        )

        self.message_repository = (
            message_repository
        )

        self.clock = clock

        self.get_conversation = GetConversation(
            conversation_repository
        )

    def execute(
        self,
        data: MarkConversationReadInput,
    ) -> MarkConversationReadResult:
        conversation = (
            self.get_conversation.execute(
                GetConversationInput(
                    conversation_id=data.conversation_id,
                    actor=data.actor,
                )
            )
        )

        count = (
            self.message_repository.mark_received_messages_read(
                conversation_id=conversation.id,
                recipient_user_id=data.actor.user_id,
                read_at=self.clock(),
            )
        )

        if type(count) is not int or count < 0:
            raise ConflictError(
                "Hasil update status baca tidak valid"
            )

        return MarkConversationReadResult(
            conversation_id=conversation.id,
            marked_count=count,
        )


class SendAttachmentMessage:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        storage: ChatAttachmentStorage,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self.message_repository = message_repository
        self.storage = storage
        self.clock = clock
        self.get_conversation = GetConversation(conversation_repository)

    def execute(self, data: SendAttachmentMessageInput) -> tuple[Message, tuple[MessageAttachment, ...]]:
        conversation = self.get_conversation.execute(
            GetConversationInput(conversation_id=data.conversation_id, actor=data.actor)
        )
        try:
            caption = normalize_message_text(data.caption, required=False)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        stored = (
            self.storage.save_image(data.source)
            if data.is_image
            else self.storage.save_document(data.source, data.file_name)
        )
        try:
            now = self.clock()
            message = Message(
                id=str(uuid4()),
                conversation_id=conversation.id,
                sender_user_id=data.actor.user_id,
                message_text=caption,
                message_type=MessageType.IMAGE if data.is_image else MessageType.FILE,
                sent_at=now,
                created_at=now,
                read_at=None,
            )
            attachment = MessageAttachment(
                id=str(uuid4()),
                message_id=message.id,
                original_file_name=_display_name(data.file_name, stored.key, data.is_image),
                storage_key=stored.key,
                mime_type=stored.mime_type,
                file_size_bytes=stored.size,
                uploaded_at=now,
            )
            try:
                saved = self.message_repository.create_with_attachments(message=message, attachments=(attachment,))
            except ValueError as exc:
                raise BadRequestError(str(exc)) from exc
            return saved, (attachment,)
        except Exception:
            self.storage.delete(stored.key)
            if stored.thumbnail_key:
                self.storage.delete(stored.thumbnail_key)
            raise


def _display_name(file_name: str, key: str, is_image: bool) -> str:
    name = (file_name or "").replace("/", "_").replace("\\", "_").replace("\x00", "").strip()[:200]
    if is_image:
        stem = name.rsplit(".", 1)[0] if "." in name else (name or "foto")
        return f"{stem or 'foto'}.webp"
    return name or key


class GetMessageAttachmentFile:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        storage: ChatAttachmentStorage,
    ):
        self.message_repository = message_repository
        self.storage = storage
        self.get_conversation = GetConversation(conversation_repository)

    def execute(self, data: GetAttachmentFileInput) -> tuple[MessageAttachment, str, BinaryIO]:
        conversation = self.get_conversation.execute(
            GetConversationInput(conversation_id=data.conversation_id, actor=data.actor)
        )
        found = self.message_repository.get_attachment(data.attachment_id)
        if found is None or found[1] != conversation.id:
            raise ChatFileNotFoundError()
        attachment = found[0]
        key = attachment.storage_key
        mime = attachment.mime_type
        if data.thumbnail:
            key = thumbnail_key_of(key)
            if key is None:
                raise ChatFileNotFoundError()
            mime = "image/webp"
        return attachment, mime, self.storage.open(key)


MAX_DELETE_BATCH = 100
DELETE_FOR_EVERYONE_WINDOW = timedelta(hours=48)


class MessageDeleteExpiredError(BadRequestError):
    code = "MESSAGE_DELETE_EXPIRED"

    def __init__(self):
        super().__init__("Pesan yang lebih dari 48 jam hanya bisa dihapus untuk saya")


class DeleteMessages:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self.message_repository = message_repository
        self.clock = clock
        self.get_conversation = GetConversation(conversation_repository)

    def execute(self, data: DeleteMessagesInput) -> DeleteMessagesResult:
        conversation = self.get_conversation.execute(
            GetConversationInput(conversation_id=data.conversation_id, actor=data.actor)
        )
        try:
            scope = MessageDeleteScope(data.scope)
        except ValueError as exc:
            raise BadRequestError("Scope hapus harus ME atau EVERYONE") from exc

        message_ids = tuple(dict.fromkeys(_validate_id(item, "Message ID") for item in data.message_ids))
        if not message_ids:
            raise BadRequestError("Pilih minimal satu pesan")
        if len(message_ids) > MAX_DELETE_BATCH:
            raise BadRequestError(f"Maksimal {MAX_DELETE_BATCH} pesan sekali hapus")

        found = {item.id: item for item in self.message_repository.list_by_ids(conversation.id, message_ids)}
        if any(message_id not in found for message_id in message_ids):
            raise NotFoundError("Pesan tidak ditemukan")

        now = self.clock()
        if scope == MessageDeleteScope.ME:
            self.message_repository.hide_for_user(message_ids, data.actor.user_id, now)
            return DeleteMessagesResult(conversation.id, scope, message_ids, now)

        messages = [found[message_id] for message_id in message_ids]
        if any(item.sender_user_id != data.actor.user_id for item in messages):
            raise ForbiddenError("Hanya pesan milik sendiri yang bisa dihapus untuk semua orang")
        targets = tuple(item.id for item in messages if item.deleted_at is None)
        if any(now - found[message_id].sent_at > DELETE_FOR_EVERYONE_WINDOW for message_id in targets):
            raise MessageDeleteExpiredError()

        removed = tuple(self.message_repository.delete_for_everyone(targets, now)) if targets else ()
        return DeleteMessagesResult(conversation.id, scope, message_ids, now, removed)
