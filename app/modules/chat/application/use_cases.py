from collections.abc import Callable
from datetime import datetime, timezone
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
)

from app.modules.chat.domain.entities import (
    ChatActor,
    Conversation,
    Message,
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

from app.modules.chat.domain.message_rules import (
    require_attachment_belongs_to_message,
    validate_message_payload,
)

from app.modules.users.domain.entities import UserRole


# ============================================================
# 1. SHARED HELPERS
# ============================================================

def _utc_now() -> datetime:
    """
    Mengambil timestamp UTC.

    Clock bisa diganti saat unit testing
    agar hasil pengujian deterministik.
    """
    return datetime.now(timezone.utc)


def _validate_id(
    value: str,
    field_name: str,
) -> str:
    """
    Mengubah kesalahan validasi Domain
    menjadi error Application.
    """
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
    """
    Actor harus berasal dari autentikasi.

    Pemeriksaan JWT sebenarnya dilakukan
    pada Presentation Layer nanti.
    """
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
    """
    Mencegah IDOR pada conversation.

    Jika pengguna bukan peserta, gunakan
    404 agar data percakapan tidak terbuka.
    """
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
    """
    Membatasi ukuran query database.
    """
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


# ============================================================
# 2. CREATE OR GET CONVERSATION
# ============================================================

class CreateOrGetConversation:
    """
    Membuat atau mengambil percakapan.

    Mendukung:
    - Chat umum tanpa project
    - Chat terkait project tertentu

    Repository harus menjamin uniqueness
    ketika ada dua request bersamaan.
    """

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

        # ====================================================
        # 1. VALIDATE COUNTERPART ROLE
        # ====================================================

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

        # ====================================================
        # 2. DETERMINE PARTICIPANTS
        # ====================================================

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

        # ====================================================
        # 3. VALIDATE PROJECT OWNERSHIP
        # ====================================================

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

        # ====================================================
        # 4. RETURN EXISTING CONVERSATION
        # ====================================================

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

        # ====================================================
        # 5. CREATE CONVERSATION
        # ====================================================

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

        # create_or_get wajib menggunakan perlindungan
        # unique constraint pada database.
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
        """
        Memastikan Repository tidak mengembalikan
        percakapan dengan peserta berbeda.
        """
        if (
            not isinstance(conversation, Conversation)
            or conversation.umkm_id != umkm_id
            or conversation.freelancer_id != freelancer_id
            or conversation.project_id != project_id
        ):
            raise ConflictError(
                "Data percakapan tidak konsisten"
            )


# ============================================================
# 3. GET CONVERSATION DETAIL
# ============================================================

class GetConversation:
    """
    Mengambil satu percakapan berdasarkan ID.

    Akses hanya untuk peserta resmi.
    """

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


# ============================================================
# 4. LIST USER CONVERSATIONS
# ============================================================

class ListUserConversations:
    """
    Mengambil daftar percakapan pengguna.

    Repository wajib melakukan filter
    berdasarkan user_id di database.
    """

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

        # ====================================================
        # DEFENSE IN DEPTH
        # ====================================================

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


# ============================================================
# 5. SEND TEXT MESSAGE
# ============================================================

class SendTextMessage:
    """
    Mengirim pesan teks.

    Sender ID selalu berasal dari actor
    yang sudah diautentikasi.

    Repository harus menyimpan pesan
    dan memperbarui last_message_at
    secara atomik.
    """

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

        # ====================================================
        # 1. VALIDATE MESSAGE TEXT
        # ====================================================

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

        # ====================================================
        # 2. PREPARE MESSAGE
        # ====================================================

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

        # ====================================================
        # 3. SAVE MESSAGE
        # ====================================================

        saved = (
            self.message_repository.create_with_attachments(
                message=message,
                attachments=(),
            )
        )

        # ====================================================
        # 4. VERIFY SAVED MESSAGE
        # ====================================================

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


# ============================================================
# 6. LIST CONVERSATION MESSAGES
# ============================================================

class ListConversationMessages:
    """
    Mengambil riwayat pesan dengan keyset pagination.

    Urutan:
        sent_at DESC, id DESC

    Menggunakan cursor untuk menghindari
    masalah pagination ketika ada pesan baru.
    """

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

        # ====================================================
        # 1. VALIDATE CURSOR
        # ====================================================

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

        # ====================================================
        # 2. GET ONE EXTRA ITEM
        # ====================================================

        fetched = tuple(
            self.message_repository.list_for_conversation(
                conversation.id,
                limit=data.limit + 1,
                before=data.before,
            )
        )

        if len(fetched) > data.limit + 1:
            raise ConflictError(
                "Repository mengembalikan "
                "terlalu banyak pesan"
            )

        has_more = len(fetched) > data.limit

        messages = fetched[:data.limit]

        # ====================================================
        # 3. VERIFY MESSAGE MEMBERSHIP
        # ====================================================

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

        # ====================================================
        # 4. FETCH ATTACHMENTS IN BULK
        # ====================================================

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

        # ====================================================
        # 5. BUILD PAGE RESULT
        # ====================================================

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


# ============================================================
# 7. MARK CONVERSATION AS READ
# ============================================================

class MarkConversationRead:
    """
    Menandai pesan dari lawan bicara
    sebagai sudah dibaca.

    Tidak boleh mengubah read_at pesan
    yang dikirim oleh pengguna sendiri.
    """

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

        # ====================================================
        # MARK ONLY RECEIVED UNREAD MESSAGES
        # ====================================================

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