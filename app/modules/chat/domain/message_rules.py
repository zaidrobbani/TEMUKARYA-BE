from collections.abc import Sequence

from app.modules.chat.domain.conversation_rules import (
    require_conversation_access,
    validate_chat_id,
)

from app.modules.chat.domain.entities import (
    ChatActor,
    Conversation,
    Message,
    MessageAttachment,
    MessageType,
)


# ============================================================
# 1. MESSAGE LIMITS
# ============================================================

MAX_TEXT_LENGTH = 4000

MAX_ATTACHMENTS = 5

MAX_FILE_BYTES = 10 * 1024 * 1024


# ============================================================
# 2. ALLOWED MIME TYPES
# ============================================================

ALLOWED_MIME_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
})

IMAGE_MIME_TYPES = frozenset(
    mime
    for mime in ALLOWED_MIME_TYPES
    if mime.startswith("image/")
)


# ============================================================
# 3. NORMALIZE MESSAGE TEXT
# ============================================================

def normalize_message_text(
    text: str | None,
    *,
    required: bool,
) -> str | None:
    """
    Membersihkan whitespace di awal/akhir pesan.

    Untuk TEXT:
        Isi pesan wajib ada.

    Untuk IMAGE/FILE:
        Caption bersifat opsional.
    """

    if text is None:
        if required:
            raise ValueError(
                "Pesan teks tidak boleh kosong"
            )

        return None

    if not isinstance(text, str):
        raise ValueError(
            "Pesan harus berupa string"
        )

    normalized = text.strip()

    if "\x00" in normalized:
        raise ValueError(
            "Pesan mengandung karakter tidak valid"
        )

    if len(normalized) > MAX_TEXT_LENGTH:
        raise ValueError(
            "Pesan terlalu panjang"
        )

    if not normalized:
        if required:
            raise ValueError(
                "Pesan teks tidak boleh kosong"
            )

        return None

    return normalized


# ============================================================
# 4. VALIDATE ATTACHMENT METADATA
# ============================================================

def validate_attachment(
    attachment: MessageAttachment,
) -> None:
    """
    Memvalidasi metadata lampiran.

    Validasi isi file sebenarnya dilakukan
    melalui Storage Module.
    """

    if not isinstance(
        attachment,
        MessageAttachment,
    ):
        raise ValueError(
            "Metadata lampiran tidak valid"
        )

    validate_chat_id(
        attachment.id,
        "Attachment ID",
    )

    validate_chat_id(
        attachment.message_id,
        "Message ID",
    )

    # --------------------------------------------------------
    # Validate file name
    # --------------------------------------------------------

    name = attachment.original_file_name

    if (
        not isinstance(name, str)
        or not name.strip()
        or len(name) > 255
        or any(
            character in name
            for character in (
                "/",
                "\\",
                "\x00",
            )
        )
        or name in (".", "..")
    ):
        raise ValueError(
            "Nama file tidak valid"
        )

    # --------------------------------------------------------
    # Validate storage key
    # --------------------------------------------------------

    key = attachment.storage_key

    if (
        not isinstance(key, str)
        or not key
        or len(key) > 500
        or "\\" in key
        or "\x00" in key
        or any(
            segment in ("", ".", "..")
            for segment in key.split("/")
        )
    ):
        raise ValueError(
            "Storage key tidak valid"
        )

    # --------------------------------------------------------
    # Validate MIME type
    # --------------------------------------------------------

    if attachment.mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(
            "Tipe file tidak diizinkan"
        )

    # --------------------------------------------------------
    # Validate file size
    # --------------------------------------------------------

    if (
        type(attachment.file_size_bytes) is not int
        or not (
            0 < attachment.file_size_bytes <= MAX_FILE_BYTES
        )
    ):
        raise ValueError(
            "Ukuran lampiran tidak valid"
        )


# ============================================================
# 5. VALIDATE MESSAGE PAYLOAD
# ============================================================

def validate_message_payload(
    message_type: MessageType,
    message_text: str | None,
    attachments: Sequence[MessageAttachment],
) -> str | None:
    """
    Memvalidasi jenis pesan dan lampirannya.

    Mengembalikan isi pesan/caption
    yang sudah dinormalisasi.
    """

    if not isinstance(
        message_type,
        MessageType,
    ):
        raise ValueError(
            "Jenis pesan tidak dikenal"
        )

    if not isinstance(
        attachments,
        (tuple, list),
    ):
        raise ValueError(
            "Daftar lampiran tidak valid"
        )

    if len(attachments) > MAX_ATTACHMENTS:
        raise ValueError(
            "Lampiran melebihi batas"
        )

    for attachment in attachments:
        validate_attachment(
            attachment
        )

    # --------------------------------------------------------
    # Text message
    # --------------------------------------------------------

    if message_type == MessageType.TEXT:

        if attachments:
            raise ValueError(
                "Pesan TEXT tidak boleh memiliki lampiran"
            )

        return normalize_message_text(
            message_text,
            required=True,
        )

    # --------------------------------------------------------
    # Image / File message
    # --------------------------------------------------------

    if not attachments:
        raise ValueError(
            "Pesan IMAGE/FILE membutuhkan lampiran"
        )

    if message_type == MessageType.IMAGE:

        if any(
            item.mime_type not in IMAGE_MIME_TYPES
            for item in attachments
        ):
            raise ValueError(
                "Lampiran IMAGE harus berupa gambar"
            )

    return normalize_message_text(
        message_text,
        required=False,
    )


# ============================================================
# 6. VALIDATE MESSAGE SENDER
# ============================================================

def require_message_sender(
    conversation: Conversation,
    actor: ChatActor,
) -> None:
    """
    Pengirim harus menjadi peserta percakapan.
    """

    require_conversation_access(
        conversation,
        actor,
    )


# ============================================================
# 7. VALIDATE MESSAGE READ STATUS
# ============================================================

def should_mark_message_read(
    conversation: Conversation,
    message: Message,
    actor: ChatActor,
) -> bool:
    """
    Hanya penerima yang boleh menandai pesan
    sebagai telah dibaca.

    True:
        Pesan belum dibaca.

    False:
        Pesan sudah dibaca sebelumnya.
    """

    require_conversation_access(
        conversation,
        actor,
    )

    if message.conversation_id != conversation.id:
        raise ValueError(
            "Pesan bukan milik percakapan"
        )

    if message.sender_user_id not in {
        conversation.umkm_id,
        conversation.freelancer_id,
    }:
        raise ValueError(
            "Pengirim pesan tidak valid"
        )

    if message.sender_user_id == actor.user_id:
        raise PermissionError(
            "Pengirim tidak boleh menandai "
            "pesannya sebagai diterima"
        )

    return message.read_at is None


# ============================================================
# 8. VERIFY ATTACHMENT MESSAGE
# ============================================================

def require_attachment_belongs_to_message(
    attachment: MessageAttachment,
    message: Message,
) -> None:
    """
    Lampiran hanya boleh digunakan
    untuk pesan pemiliknya.
    """

    validate_attachment(
        attachment
    )

    if attachment.message_id != message.id:
        raise ValueError(
            "Lampiran bukan milik pesan"
        )