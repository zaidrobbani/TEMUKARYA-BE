from datetime import datetime, timezone
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
)

from app.modules.chat.domain.conversation_rules import (
    validate_conversation_participants,
)

from app.modules.chat.domain.entities import (
    Conversation,
    Message,
    MessageAttachment,
    MessageType,
)

from app.modules.chat.domain.message_rules import (
    require_attachment_belongs_to_message,
    validate_message_payload,
)

from app.modules.chat.infrastructure.models import (
    ConversationModel,
)


# ============================================================
# 1. DATETIME HELPERS
# ============================================================

def _db_time(value: datetime) -> datetime:
    """
    Simpan timestamp aplikasi sebagai UTC-naive
    karena MySQL DATETIME tidak menyimpan timezone.
    """

    if not isinstance(value, datetime):
        raise ValueError("Timestamp tidak valid")

    if value.tzinfo is not None:
        return value.astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    return value


def _read_time(
    value: datetime | str | None,
) -> datetime | None:
    """
    Konversi DATETIME database menjadi UTC-aware.
    """

    if value is None:
        return None

    if isinstance(value, str):
        value = datetime.fromisoformat(value)

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


# ============================================================
# 2. ROW MAPPERS
# ============================================================

def _conversation_from_row(
    row: Any,
) -> Conversation:

    return Conversation(
        id=str(row["id"]),
        umkm_id=str(row["umkm_id"]),
        freelancer_id=str(row["freelancer_id"]),
        project_id=(
            str(row["project_id"])
            if row["project_id"] is not None
            else None
        ),
        last_message_at=_read_time(
            row["last_message_at"]
        ),
        created_at=_read_time(
            row["created_at"]
        ),
        updated_at=_read_time(
            row["updated_at"]
        ),
    )


def _message_from_row(
    row: Any,
) -> Message:

    return Message(
        id=str(row["id"]),
        conversation_id=str(row["conversation_id"]),
        sender_user_id=str(row["sender_user_id"]),
        message_text=row["message_text"],
        message_type=MessageType(
            row["message_type"]
        ),
        sent_at=_read_time(row["sent_at"]),
        created_at=_read_time(row["created_at"]),
        read_at=_read_time(row["read_at"]),
    )


def _attachment_from_row(
    row: Any,
) -> MessageAttachment:

    return MessageAttachment(
        id=str(row["id"]),
        message_id=str(row["message_id"]),
        original_file_name=row["original_file_name"],
        storage_key=row["storage_key"],
        mime_type=row["mime_type"],
        file_size_bytes=int(row["file_size_bytes"]),
        uploaded_at=_read_time(
            row["uploaded_at"]
        ),
    )


# ============================================================
# 3. CONVERSATION REPOSITORY
# ============================================================

class SqlAlchemyConversationRepository:
    """
    Implementasi ConversationRepository.

    Repository tidak melakukan commit().
    Pemanggil bertanggung jawab atas transaksi.
    """

    def __init__(
        self,
        session: Session,
    ):
        self._session = session

    # ========================================================
    # A. INTERNAL FIND CONVERSATION
    # ========================================================

    def _find(
        self,
        umkm_id: str,
        freelancer_id: str,
        project_id: str | None,
        *,
        lock: bool = False,
    ) -> Conversation | None:

        project_condition = (
            "project_id IS NULL"
            if project_id is None
            else "project_id = :project_id"
        )

        lock_sql = (
            " FOR UPDATE"
            if (
                lock
                and self._session.get_bind().dialect.name
                in ("mysql", "mariadb")
            )
            else ""
        )

        statement = text(
            "SELECT id, umkm_id, freelancer_id, "
            "project_id, last_message_at, "
            "created_at, updated_at "
            "FROM conversations "
            "WHERE umkm_id = :umkm_id "
            "AND freelancer_id = :freelancer_id "
            "AND " + project_condition + lock_sql
        )

        row = self._session.execute(
            statement,
            {
                "umkm_id": umkm_id,
                "freelancer_id": freelancer_id,
                "project_id": project_id,
            },
        ).mappings().one_or_none()

        return (
            _conversation_from_row(row)
            if row is not None
            else None
        )

    # ========================================================
    # B. FIND BY PARTICIPANTS
    # ========================================================

    def find_by_participants(
        self,
        umkm_id: str,
        freelancer_id: str,
        project_id: str | None,
    ) -> Conversation | None:

        return self._find(
            umkm_id,
            freelancer_id,
            project_id,
        )

    # ========================================================
    # C. GET CONVERSATION BY ID
    # ========================================================

    def get_by_id(
        self,
        conversation_id: str,
    ) -> Conversation | None:

        statement = text(
            "SELECT id, umkm_id, freelancer_id, "
            "project_id, last_message_at, "
            "created_at, updated_at "
            "FROM conversations "
            "WHERE id = :conversation_id"
        )

        row = self._session.execute(
            statement,
            {
                "conversation_id": conversation_id,
            },
        ).mappings().one_or_none()

        return (
            _conversation_from_row(row)
            if row is not None
            else None
        )

    # ========================================================
    # D. LIST CONVERSATIONS FOR USER
    # ========================================================

    def list_for_user(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[Conversation, ...]:

        statement = text(
            "SELECT id, umkm_id, freelancer_id, "
            "project_id, last_message_at, "
            "created_at, updated_at "
            "FROM conversations "
            "WHERE umkm_id = :user_id "
            "OR freelancer_id = :user_id "
            "ORDER BY "
            "COALESCE(last_message_at, created_at) DESC, "
            "id DESC "
            "LIMIT :limit OFFSET :offset"
        )

        rows = self._session.execute(
            statement,
            {
                "user_id": user_id,
                "limit": limit,
                "offset": offset,
            },
        ).mappings().all()

        return tuple(
            _conversation_from_row(row)
            for row in rows
        )

    # ========================================================
    # E. GET USER ROLE
    # ========================================================

    def get_user_role(
        self,
        user_id: str,
    ) -> str | None:

        return self._session.execute(
            text(
                "SELECT role FROM users "
                "WHERE id = :user_id"
            ),
            {
                "user_id": user_id,
            },
        ).scalar_one_or_none()

    # ========================================================
    # F. GET PROJECT OWNER
    # ========================================================

    def get_project_owner_id(
        self,
        project_id: str,
    ) -> str | None:

        owner_id = self._session.execute(
            text(
                "SELECT umkm_id FROM projects "
                "WHERE id = :project_id"
            ),
            {
                "project_id": project_id,
            },
        ).scalar_one_or_none()

        return (
            str(owner_id)
            if owner_id is not None
            else None
        )

    # ========================================================
    # G. CREATE OR GET CONVERSATION
    # ========================================================

    def create_or_get(
        self,
        conversation: Conversation,
    ) -> Conversation:
        """
        Menangani duplicate conversation secara atomik
        menggunakan UNIQUE constraint database.

        MySQL: ON DUPLICATE KEY UPDATE
        SQLite: ON CONFLICT DO NOTHING

        Tidak membuat migration baru.
        """

        validate_conversation_participants(
            conversation.umkm_id,
            conversation.freelancer_id,
            conversation.project_id,
        )

        dialect = (
            self._session.get_bind().dialect.name
        )

        values = {
            "id": conversation.id,
            "umkm_id": conversation.umkm_id,
            "freelancer_id": conversation.freelancer_id,
            "project_id": conversation.project_id,
            "last_message_at": (
                _db_time(conversation.last_message_at)
                if conversation.last_message_at is not None
                else None
            ),
            "created_at": _db_time(
                conversation.created_at
            ),
            "updated_at": _db_time(
                conversation.updated_at
            ),
        }

        if dialect in ("mysql", "mariadb"):

            statement = mysql_insert(
                ConversationModel
            ).values(**values)

            statement = (
                statement.on_duplicate_key_update(
                    id=ConversationModel.id
                )
            )

        elif dialect == "sqlite":

            statement = sqlite_insert(
                ConversationModel
            ).values(**values)

            statement = (
                statement.on_conflict_do_nothing()
            )

        else:
            raise ConflictError(
                "Dialect database Chat belum didukung"
            )

        # INSERT memakai constraint database agar
        # dua request bersamaan tidak membuat
        # dua percakapan yang sama.
        with self._session.begin_nested():
            self._session.execute(statement)

        # Locking read pada MySQL digunakan untuk
        # membaca percakapan hasil insert/upsert.
        existing = self._find(
            conversation.umkm_id,
            conversation.freelancer_id,
            conversation.project_id,
            lock=True,
        )

        if existing is None:
            raise ConflictError(
                "Gagal mengambil percakapan "
                "yang disimpan"
            )

        return existing


# ============================================================
# 4. MESSAGE REPOSITORY
# ============================================================

class SqlAlchemyMessageRepository:
    """
    Implementasi MessageRepository.

    Transaksi utama tetap dimiliki pemanggil.
    """

    def __init__(
        self,
        session: Session,
    ):
        self._session = session

    # ========================================================
    # A. LIST MESSAGES WITH KEYSET PAGINATION
    # ========================================================

    def list_for_conversation(
        self,
        conversation_id: str,
        *,
        limit: int,
        before: tuple[datetime, str] | None = None,
    ) -> tuple[Message, ...]:

        cursor_condition = ""

        params = {
            "conversation_id": conversation_id,
            "limit": limit,
        }

        if before is not None:

            cursor_condition = (
                " AND (sent_at < :before_at "
                "OR (sent_at = :before_at "
                "AND id < :before_id))"
            )

            params["before_at"] = _db_time(
                before[0]
            )
            params["before_id"] = before[1]

        statement = text(
            "SELECT id, conversation_id, "
            "sender_user_id, message_text, "
            "message_type, sent_at, created_at, read_at "
            "FROM messages "
            "WHERE conversation_id = :conversation_id "
            + cursor_condition
            + " ORDER BY sent_at DESC, id DESC "
            "LIMIT :limit"
        )

        rows = self._session.execute(
            statement,
            params,
        ).mappings().all()

        return tuple(
            _message_from_row(row)
            for row in rows
        )

    # ========================================================
    # B. GET MESSAGE BY ID
    # ========================================================

    def get_by_id(
        self,
        message_id: str,
    ) -> Message | None:

        statement = text(
            "SELECT id, conversation_id, "
            "sender_user_id, message_text, "
            "message_type, sent_at, created_at, read_at "
            "FROM messages "
            "WHERE id = :message_id"
        )

        row = self._session.execute(
            statement,
            {
                "message_id": message_id,
            },
        ).mappings().one_or_none()

        return (
            _message_from_row(row)
            if row is not None
            else None
        )

    # ========================================================
    # C. LIST MESSAGE ATTACHMENTS
    # ========================================================

    def list_attachments(
        self,
        message_ids: tuple[str, ...],
    ) -> tuple[MessageAttachment, ...]:

        if not message_ids:
            return ()

        statement = text(
            "SELECT id, message_id, "
            "original_file_name, storage_key, "
            "mime_type, file_size_bytes, uploaded_at "
            "FROM message_attachments "
            "WHERE message_id IN :ids "
            "ORDER BY message_id ASC, id ASC"
        ).bindparams(
            bindparam(
                "ids",
                expanding=True,
            )
        )

        rows = self._session.execute(
            statement,
            {
                "ids": message_ids,
            },
        ).mappings().all()

        return tuple(
            _attachment_from_row(row)
            for row in rows
        )

    # ========================================================
    # D. CREATE MESSAGE WITH ATTACHMENTS
    # ========================================================

    def create_with_attachments(
        self,
        message: Message,
        attachments: tuple[MessageAttachment, ...],
    ) -> Message:
        """
        Menyimpan pesan, lampiran, dan memperbarui
        waktu pesan terakhir dalam satu savepoint.

        Commit transaksi utama dilakukan oleh caller.
        """

        normalized_text = validate_message_payload(
            message.message_type,
            message.message_text,
            attachments,
        )

        if message.message_text != normalized_text:
            raise ValueError(
                "Pesan harus dinormalisasi "
                "sebelum disimpan"
            )

        for attachment in attachments:
            require_attachment_belongs_to_message(
                attachment,
                message,
            )

        # Pastikan pengirim adalah peserta conversation.
        statement = text(
            "SELECT umkm_id, freelancer_id "
            "FROM conversations "
            "WHERE id = :conversation_id"
        )

        participants = self._session.execute(
            statement,
            {
                "conversation_id": message.conversation_id,
            },
        ).mappings().one_or_none()

        if (
            participants is None
            or message.sender_user_id not in (
                participants["umkm_id"],
                participants["freelancer_id"],
            )
        ):
            raise NotFoundError(
                "Percakapan tidak ditemukan"
            )

        sent_at = _db_time(message.sent_at)

        # ====================================================
        # ATOMIC SAVEPOINT
        # ====================================================

        with self._session.begin_nested():

            # ------------------------------------------------
            # 1. INSERT MESSAGE
            # ------------------------------------------------

            self._session.execute(
                text(
                    "INSERT INTO messages "
                    "(id, conversation_id, sender_user_id, "
                    "message_text, message_type, "
                    "sent_at, read_at, created_at) "
                    "VALUES "
                    "(:id, :conversation_id, :sender_user_id, "
                    ":message_text, :message_type, "
                    ":sent_at, :read_at, :created_at)"
                ),
                {
                    "id": message.id,
                    "conversation_id": message.conversation_id,
                    "sender_user_id": message.sender_user_id,
                    "message_text": message.message_text,
                    "message_type": message.message_type.value,
                    "sent_at": sent_at,
                    "read_at": (
                        _db_time(message.read_at)
                        if message.read_at is not None
                        else None
                    ),
                    "created_at": _db_time(
                        message.created_at
                    ),
                },
            )

            # ------------------------------------------------
            # 2. INSERT ATTACHMENTS
            # ------------------------------------------------

            for attachment in attachments:

                self._session.execute(
                    text(
                        "INSERT INTO message_attachments "
                        "(id, message_id, original_file_name, "
                        "storage_key, mime_type, "
                        "file_size_bytes, uploaded_at) "
                        "VALUES "
                        "(:id, :message_id, :file_name, "
                        ":storage_key, :mime, "
                        ":file_size, :uploaded_at)"
                    ),
                    {
                        "id": attachment.id,
                        "message_id": message.id,
                        "file_name": (
                            attachment.original_file_name
                        ),
                        "storage_key": attachment.storage_key,
                        "mime": attachment.mime_type,
                        "file_size": attachment.file_size_bytes,
                        "uploaded_at": _db_time(
                            attachment.uploaded_at
                        ),
                    },
                )

            # ------------------------------------------------
            # 3. UPDATE CONVERSATION ACTIVITY
            # ------------------------------------------------

            self._session.execute(
                text(
                    "UPDATE conversations SET "
                    "last_message_at = CASE "
                    "WHEN last_message_at IS NULL "
                    "OR last_message_at < :sent_at "
                    "THEN :sent_at "
                    "ELSE last_message_at END, "
                    "updated_at = CASE "
                    "WHEN updated_at < :sent_at "
                    "THEN :sent_at "
                    "ELSE updated_at END "
                    "WHERE id = :conversation_id"
                ),
                {
                    "sent_at": sent_at,
                    "conversation_id": message.conversation_id,
                },
            )

        return message

    # ========================================================
    # E. MARK RECEIVED MESSAGES AS READ
    # ========================================================

    def mark_received_messages_read(
        self,
        conversation_id: str,
        recipient_user_id: str,
        read_at: datetime,
    ) -> int:
        """
        Hanya update pesan dari lawan bicara
        yang belum pernah dibaca.

        Operasi berulang menjadi idempotent.
        """

        participants = self._session.execute(
            text(
                "SELECT umkm_id, freelancer_id "
                "FROM conversations "
                "WHERE id = :conversation_id"
            ),
            {
                "conversation_id": conversation_id,
            },
        ).mappings().one_or_none()

        if (
            participants is None
            or recipient_user_id not in (
                participants["umkm_id"],
                participants["freelancer_id"],
            )
        ):
            raise NotFoundError(
                "Percakapan tidak ditemukan"
            )

        statement = text(
            "UPDATE messages "
            "SET read_at = :read_at "
            "WHERE conversation_id = :conversation_id "
            "AND read_at IS NULL "
            "AND sender_user_id != :recipient_id "
            "AND sender_user_id "
            "IN (:umkm_id, :freelancer_id)"
        )

        result = self._session.execute(
            statement,
            {
                "read_at": _db_time(read_at),
                "conversation_id": conversation_id,
                "recipient_id": recipient_user_id,
                "umkm_id": participants["umkm_id"],
                "freelancer_id": participants["freelancer_id"],
            },
        )

        return result.rowcount