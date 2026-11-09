from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.modules.chat.domain.entities import (
    ChatActor,
    Conversation,
    Message,
    MessageAttachment,
    MessageType,
)

from app.modules.chat.domain.message_rules import (
    MAX_TEXT_LENGTH,
    MAX_FILE_BYTES,
    normalize_message_text,
    validate_attachment,
    validate_message_payload,
    require_message_sender,
    should_mark_message_read,
    require_attachment_belongs_to_message,
)


# ============================================================
# TEST DATA
# ============================================================

NOW = datetime(
    2026, 11, 4,
    tzinfo=timezone.utc,
)

CONV = Conversation(
    "c1", "u1", "f1",
    None, NOW, NOW, NOW,
)

UMKM = ChatActor(
    "u1", "UMKM"
)

FREELANCER = ChatActor(
    "f1", "FREELANCER"
)


# ============================================================
# TEST HELPERS
# ============================================================

def msg(read_at=None):
    return Message(
        "m1",
        "c1",
        "u1",
        "Halo",
        MessageType.TEXT,
        NOW,
        NOW,
        read_at,
    )


def att(mime="image/png"):
    return MessageAttachment(
        "a1",
        "m1",
        "photo.png",
        "chat/m1/photo.png",
        mime,
        1024,
        NOW,
    )


# ============================================================
# 1. MESSAGE TEXT
# ============================================================

def test_normalize_text():
    assert normalize_message_text(
        "  halo\n ",
        required=True,
    ) == "halo"


def test_optional_blank_caption():
    assert normalize_message_text(
        "   ",
        required=False,
    ) is None


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "   ",
        "\n\t",
    ],
)
def test_required_text_rejects_empty(text):
    with pytest.raises(ValueError):
        normalize_message_text(
            text,
            required=True,
        )


@pytest.mark.parametrize(
    "text",
    [
        99,
        "a\x00b",
        "a" * (MAX_TEXT_LENGTH + 1),
    ],
)
def test_invalid_text(text):
    with pytest.raises(ValueError):
        normalize_message_text(
            text,
            required=True,
        )


def test_max_text_length_accepted():
    assert len(
        normalize_message_text(
            "a" * MAX_TEXT_LENGTH,
            required=True,
        )
    ) == MAX_TEXT_LENGTH


# ============================================================
# 2. ATTACHMENT VALIDATION
# ============================================================

def test_validate_image_attachment():
    validate_attachment(att())


def test_validate_pdf_attachment():
    validate_attachment(
        att("application/pdf")
    )


@pytest.mark.parametrize(
    "bad",
    [
        "../secret.png",
        "a/b.png",
        "a\\b.png",
        "",
        "x" * 256,
    ],
)
def test_invalid_filename(bad):
    with pytest.raises(ValueError):
        validate_attachment(
            replace(
                att(),
                original_file_name=bad,
            )
        )


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "../secret",
        "chat/../secret",
        "chat//file",
        "chat\\file",
    ],
)
def test_invalid_storage_key(bad):
    with pytest.raises(ValueError):
        validate_attachment(
            replace(
                att(),
                storage_key=bad,
            )
        )


def test_invalid_mime_rejected():
    with pytest.raises(ValueError):
        validate_attachment(
            att("application/x-msdownload")
        )


@pytest.mark.parametrize(
    "size",
    [
        0,
        -1,
        MAX_FILE_BYTES + 1,
        True,
        4.5,
    ],
)
def test_bad_size_rejected(size):
    with pytest.raises(ValueError):
        validate_attachment(
            replace(
                att(),
                file_size_bytes=size,
            )
        )


# ============================================================
# 3. MESSAGE PAYLOAD VALIDATION
# ============================================================

def test_text_payload():
    assert validate_message_payload(
        MessageType.TEXT,
        " hello ",
        [],
    ) == "hello"


def test_text_payload_rejects_attachment():
    with pytest.raises(ValueError):
        validate_message_payload(
            MessageType.TEXT,
            "hello",
            [att()],
        )


def test_image_payload_with_caption():
    assert validate_message_payload(
        MessageType.IMAGE,
        " caption ",
        [att()],
    ) == "caption"


def test_file_payload_optional_caption():
    assert validate_message_payload(
        MessageType.FILE,
        None,
        [att("application/pdf")],
    ) is None


def test_image_payload_rejects_pdf():
    with pytest.raises(ValueError):
        validate_message_payload(
            MessageType.IMAGE,
            None,
            [att("application/pdf")],
        )


@pytest.mark.parametrize(
    "type_",
    [
        MessageType.IMAGE,
        MessageType.FILE,
    ],
)
def test_attachment_message_needs_file(type_):
    with pytest.raises(ValueError):
        validate_message_payload(
            type_,
            None,
            [],
        )


def test_reject_unknown_message_type():
    with pytest.raises(ValueError):
        validate_message_payload(
            "VIDEO",
            "test",
            [],
        )


def test_reject_too_many_attachments():
    with pytest.raises(ValueError):
        validate_message_payload(
            MessageType.FILE,
            None,
            [att()] * 6,
        )


# ============================================================
# 4. MESSAGE SENDER AUTHORIZATION
# ============================================================

def test_sender_is_member():
    require_message_sender(CONV, UMKM)
    require_message_sender(CONV, FREELANCER)


def test_sender_outsider_rejected():
    with pytest.raises(PermissionError):
        require_message_sender(
            CONV,
            ChatActor("other", "UMKM"),
        )


# ============================================================
# 5. MESSAGE READ STATUS
# ============================================================

def test_recipient_mark_read():
    assert should_mark_message_read(
        CONV,
        msg(),
        FREELANCER,
    ) is True


def test_mark_read_idempotent():
    assert should_mark_message_read(
        CONV,
        msg(NOW),
        FREELANCER,
    ) is False


def test_sender_cannot_mark_own_read():
    with pytest.raises(PermissionError):
        should_mark_message_read(
            CONV,
            msg(),
            UMKM,
        )


def test_outsider_cannot_mark_read():
    with pytest.raises(PermissionError):
        should_mark_message_read(
            CONV,
            msg(),
            ChatActor("other", "UMKM"),
        )


def test_message_wrong_conversation_rejected():
    with pytest.raises(ValueError):
        should_mark_message_read(
            CONV,
            replace(
                msg(),
                conversation_id="wrong",
            ),
            FREELANCER,
        )


def test_forged_sender_rejected():
    with pytest.raises(ValueError):
        should_mark_message_read(
            CONV,
            replace(
                msg(),
                sender_user_id="other",
            ),
            FREELANCER,
        )


# ============================================================
# 6. ATTACHMENT OWNERSHIP
# ============================================================

def test_attachment_message_match():
    require_attachment_belongs_to_message(
        att(),
        msg(),
    )


def test_attachment_message_mismatch():
    with pytest.raises(ValueError):
        require_attachment_belongs_to_message(
            replace(
                att(),
                message_id="different",
            ),
            msg(),
        )