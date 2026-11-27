from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.modules.chat.domain.entities import (
    ChatActor,
    Conversation,
    Message,
    MessageAttachment,
    MessageType,
)


NOW = datetime(
    2026, 11, 4, 8,
    tzinfo=timezone.utc,
)


def test_message_type_values():
    assert [
        item.value
        for item in MessageType
    ] == [
        "TEXT",
        "IMAGE",
        "FILE",
    ]


def test_chat_actor():
    actor = ChatActor("u1", "UMKM")

    assert actor.user_id == "u1"
    assert actor.role == "UMKM"


def test_general_conversation():
    data = Conversation(
        "c1", "u1", "f1",
        None, None, NOW, NOW,
    )

    assert data.project_id is None
    assert data.last_message_at is None


def test_project_conversation():
    data = Conversation(
        "c1", "u1", "f1",
        "p1", NOW, NOW, NOW,
    )

    assert data.project_id == "p1"


def test_text_message():
    msg = Message(
        "m1", "c1", "u1",
        "Halo", MessageType.TEXT,
        NOW, NOW,
    )

    assert msg.message_text == "Halo"
    assert msg.read_at is None


def test_read_message():
    msg = Message(
        "m1", "c1", "u1",
        "Halo", MessageType.TEXT,
        NOW, NOW, NOW,
    )

    assert msg.read_at == NOW


def test_attachment():
    item = MessageAttachment(
        "a1",
        "m1",
        "report.pdf",
        "chat/m1/report.pdf",
        "application/pdf",
        42,
        NOW,
    )

    assert item.file_size_bytes == 42


def test_domain_entities_immutable():
    conv = Conversation(
        "c1", "u1", "f1",
        None, None, NOW, NOW,
    )

    with pytest.raises(FrozenInstanceError):
        conv.umkm_id = "other"
