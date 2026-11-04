from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError

from app.modules.chat.domain.entities import (
    Conversation,
    Message,
    MessageAttachment,
    MessageType,
)

from app.modules.chat.infrastructure.models import (
    ConversationModel,
    MessageModel,
    MessageAttachmentModel,
)

from app.modules.chat.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)


# ============================================================
# 1. TEST CONSTANTS
# ============================================================

NOW = datetime(
    2026, 11, 4, 10, 0,
    tzinfo=timezone.utc,
)


# ============================================================
# 2. SQLITE TEST DATABASE
# ============================================================

@pytest.fixture
def db():

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    with engine.begin() as conn:

        conn.execute(
            text("""
                CREATE TABLE users (
                    id TEXT PRIMARY KEY,
                    role TEXT NOT NULL
                )
            """)
        )

        conn.execute(
            text("""
                CREATE TABLE projects (
                    id TEXT PRIMARY KEY,
                    umkm_id TEXT NOT NULL
                )
            """)
        )

        conn.execute(
            text("""
                CREATE TABLE conversations (
                    id TEXT PRIMARY KEY,
                    umkm_id TEXT NOT NULL,
                    freelancer_id TEXT NOT NULL,
                    project_id TEXT,
                    project_key TEXT GENERATED ALWAYS AS (
                        coalesce(project_id, '')
                    ) STORED,
                    last_message_at DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,

                    UNIQUE (
                        umkm_id,
                        freelancer_id,
                        project_key
                    )
                )
            """)
        )

        conn.execute(
            text("""
                CREATE TABLE messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    sender_user_id TEXT NOT NULL,
                    message_text TEXT,
                    message_type TEXT NOT NULL
                        DEFAULT 'TEXT',
                    sent_at DATETIME NOT NULL,
                    read_at DATETIME,
                    created_at DATETIME NOT NULL,

                    CHECK (
                        message_type <> 'TEXT'
                        OR message_text IS NOT NULL
                    )
                )
            """)
        )

        conn.execute(
            text("""
                CREATE TABLE message_attachments (
                    id TEXT PRIMARY KEY,
                    message_id TEXT NOT NULL,
                    original_file_name TEXT NOT NULL,
                    storage_key TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    uploaded_at DATETIME NOT NULL
                )
            """)
        )

        conn.execute(
            text("""
                INSERT INTO users
                VALUES
                    ('u1', 'umkm'),
                    ('u2', 'umkm'),
                    ('f1', 'freelancer'),
                    ('f2', 'freelancer')
            """)
        )

        conn.execute(
            text("""
                INSERT INTO projects
                VALUES ('p1', 'u1')
            """)
        )

    try:
        with Session(engine) as session:

            yield (
                session,
                SqlAlchemyConversationRepository(
                    session
                ),
                SqlAlchemyMessageRepository(
                    session
                ),
            )

    finally:
        engine.dispose()


# ============================================================
# 3. TEST DATA HELPERS
# ============================================================

def conv(
    id="c1",
    project_id=None,
    freelancer_id="f1",
):
    return Conversation(
        id=id,
        umkm_id="u1",
        freelancer_id=freelancer_id,
        project_id=project_id,
        last_message_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def message(
    id,
    sender="u1",
    at=NOW,
    conversation_id="c1",
):
    return Message(
        id=id,
        conversation_id=conversation_id,
        sender_user_id=sender,
        message_text=f"hi {id}",
        message_type=MessageType.TEXT,
        sent_at=at,
        created_at=at,
    )


# ============================================================
# 4. MODEL METADATA
# ============================================================

def test_model_metadata():

    assert (
        ConversationModel
        .__table__
        .c.project_key.computed
        is not None
    )

    assert len(
        ConversationModel
        .__table__
        .c.umkm_id.foreign_keys
    ) == 1

    assert MessageModel.__table__.c.read_at.nullable

    assert (
        MessageAttachmentModel
        .__table__
        .c.message_id.foreign_keys
    )


# ============================================================
# 5. USER ROLES AND PROJECT OWNER
# ============================================================

def test_user_roles_and_project_owner(db):

    _, conv_repo, _ = db

    assert conv_repo.get_user_role("u1") == "umkm"

    assert conv_repo.get_user_role("f1") == "freelancer"

    assert conv_repo.get_user_role("missing") is None

    assert conv_repo.get_project_owner_id("p1") == "u1"

    assert conv_repo.get_project_owner_id("missing") is None


# ============================================================
# 6. CREATE OR GET GENERAL CONVERSATION
# ============================================================

def test_create_or_get_general_conversation(db):

    session, conv_repo, _ = db

    first = conv_repo.create_or_get(
        conv()
    )

    second = conv_repo.create_or_get(
        replace(
            conv(),
            id="different",
        )
    )

    assert first.id == second.id == "c1"

    count = session.execute(
        text(
            "SELECT COUNT(*) FROM conversations"
        )
    ).scalar_one()

    assert count == 1
    assert first.project_id is None


# ============================================================
# 7. PROJECT CONVERSATION IS DIFFERENT
# ============================================================

def test_project_conversation_distinct_from_general(db):

    _, conv_repo, _ = db

    first = conv_repo.create_or_get(
        conv()
    )

    project = conv_repo.create_or_get(
        conv("c2", "p1")
    )

    assert first.id != project.id

    assert conv_repo.find_by_participants(
        "u1",
        "f1",
        None,
    ).id == "c1"

    assert conv_repo.find_by_participants(
        "u1",
        "f1",
        "p1",
    ).id == "c2"


# ============================================================
# 8. GET CONVERSATION
# ============================================================

def test_get_missing_and_get_by_id(db):

    _, conv_repo, _ = db

    assert conv_repo.get_by_id("missing") is None

    conv_repo.create_or_get(
        conv()
    )

    assert conv_repo.get_by_id(
        "c1"
    ).freelancer_id == "f1"


# ============================================================
# 9. PRIVATE CONVERSATION LIST
# ============================================================

def test_list_conversations_private_and_ordered(db):

    _, conv_repo, message_repo = db

    conv_repo.create_or_get(
        conv()
    )

    conv_repo.create_or_get(
        conv(
            "c2",
            freelancer_id="f2",
        )
    )

    message_repo.create_with_attachments(
        message(
            "m1",
            at=NOW + timedelta(minutes=1),
        ),
        (),
    )

    items = conv_repo.list_for_user(
        "u1",
        limit=10,
        offset=0,
    )

    assert [
        item.id
        for item in items
    ] == ["c1", "c2"]

    assert [
        item.id
        for item in conv_repo.list_for_user(
            "f1",
            limit=10,
            offset=0,
        )
    ] == ["c1"]

    assert conv_repo.list_for_user(
        "u2",
        limit=10,
        offset=0,
    ) == ()

    assert [
        item.id
        for item in conv_repo.list_for_user(
            "u1",
            limit=1,
            offset=1,
        )
    ] == ["c2"]


# ============================================================
# 10. SEND MESSAGE
# ============================================================

def test_send_message_updates_last_message_at(db):

    _, conv_repo, message_repo = db

    conv_repo.create_or_get(
        conv()
    )

    saved = message_repo.create_with_attachments(
        message("m1"),
        (),
    )

    assert saved.id == "m1"

    assert message_repo.get_by_id(
        "m1"
    ).sent_at == NOW

    assert conv_repo.get_by_id(
        "c1"
    ).last_message_at == NOW


# ============================================================
# 11. REJECT INVALID SENDER
# ============================================================

def test_sender_must_be_participant(db):

    _, conv_repo, message_repo = db

    conv_repo.create_or_get(
        conv()
    )

    with pytest.raises(NotFoundError):

        message_repo.create_with_attachments(
            message(
                "m1",
                sender="u2",
            ),
            (),
        )

    assert message_repo.get_by_id("m1") is None


# ============================================================
# 12. MESSAGE HISTORY PAGINATION
# ============================================================

def test_message_history_keyset(db):

    _, conv_repo, message_repo = db

    conv_repo.create_or_get(
        conv()
    )

    for i in range(3):

        msg = message(
            f"m{i}",
            at=NOW + timedelta(seconds=i),
        )

        message_repo.create_with_attachments(
            msg,
            (),
        )

    first = message_repo.list_for_conversation(
        "c1",
        limit=2,
    )

    assert [
        item.id
        for item in first
    ] == ["m2", "m1"]

    second = message_repo.list_for_conversation(
        "c1",
        limit=2,
        before=(
            first[-1].sent_at,
            first[-1].id,
        ),
    )

    assert [
        item.id
        for item in second
    ] == ["m0"]


# ============================================================
# 13. MESSAGE ORDER WITH SAME TIMESTAMP
# ============================================================

def test_message_history_tie_breaks_id(db):

    _, conv_repo, message_repo = db

    conv_repo.create_or_get(
        conv()
    )

    message_repo.create_with_attachments(
        message("m1"),
        (),
    )

    message_repo.create_with_attachments(
        message("m2"),
        (),
    )

    first = message_repo.list_for_conversation(
        "c1",
        limit=1,
    )

    second = message_repo.list_for_conversation(
        "c1",
        limit=1,
        before=(
            first[-1].sent_at,
            first[-1].id,
        ),
    )

    assert first[0].id == "m2"
    assert second[0].id == "m1"


# ============================================================
# 14. ATTACHMENT METADATA
# ============================================================

def test_attachment_metadata(db):

    _, conv_repo, message_repo = db

    conv_repo.create_or_get(
        conv()
    )

    source = Message(
        id="m1",
        conversation_id="c1",
        sender_user_id="u1",
        message_text=None,
        message_type=MessageType.FILE,
        sent_at=NOW,
        created_at=NOW,
    )

    attachment = MessageAttachment(
        id="a1",
        message_id="m1",
        original_file_name="file.pdf",
        storage_key="chat/m1/file.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        uploaded_at=NOW,
    )

    message_repo.create_with_attachments(
        source,
        (attachment,),
    )

    assert [
        item.id
        for item in message_repo.list_attachments(
            ("m1",)
        )
    ] == ["a1"]

    assert message_repo.list_attachments(
        ()
    ) == ()

    assert message_repo.get_by_id(
        "m1"
    ).message_type == MessageType.FILE


# ============================================================
# 15. FAILED ATTACHMENT ROLLS BACK MESSAGE
# ============================================================

def test_invalid_attachment_rolls_back_message(db):

    _, conv_repo, message_repo = db

    conv_repo.create_or_get(
        conv()
    )

    source = Message(
        id="m1",
        conversation_id="c1",
        sender_user_id="u1",
        message_text=None,
        message_type=MessageType.FILE,
        sent_at=NOW,
        created_at=NOW,
    )

    attachment = MessageAttachment(
        id="a1",
        message_id="m1",
        original_file_name="file.pdf",
        storage_key="chat/m1/file.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        uploaded_at=NOW,
    )

    # Dua attachment dengan primary key sama.
    # INSERT kedua harus gagal dan rollback
    # seluruh savepoint.
    with pytest.raises(Exception):

        message_repo.create_with_attachments(
            source,
            (attachment, attachment),
        )

    assert message_repo.get_by_id("m1") is None

    assert message_repo.list_attachments(
        ("m1",)
    ) == ()

    assert conv_repo.get_by_id(
        "c1"
    ).last_message_at is None


# ============================================================
# 16. MARK MESSAGES READ
# ============================================================

def test_mark_received_read_and_idempotent(db):

    _, conv_repo, message_repo = db

    conv_repo.create_or_get(
        conv()
    )

    message_repo.create_with_attachments(
        message(
            "m1",
            sender="u1",
        ),
        (),
    )

    message_repo.create_with_attachments(
        message(
            "m2",
            sender="f1",
        ),
        (),
    )

    first = message_repo.mark_received_messages_read(
        "c1",
        "u1",
        NOW,
    )

    second = message_repo.mark_received_messages_read(
        "c1",
        "u1",
        NOW,
    )

    assert first == 1
    assert second == 0

    assert message_repo.get_by_id(
        "m1"
    ).read_at is None

    assert message_repo.get_by_id(
        "m2"
    ).read_at == NOW


# ============================================================
# 17. OUTSIDER CANNOT MARK READ
# ============================================================

def test_outsider_cannot_mark_read(db):

    _, conv_repo, message_repo = db

    conv_repo.create_or_get(
        conv()
    )

    with pytest.raises(NotFoundError):

        message_repo.mark_received_messages_read(
            "c1",
            "u2",
            NOW,
        )


# ============================================================
# 18. PREVENT LAST MESSAGE TIME REGRESSION
# ============================================================

def test_updated_timestamp_does_not_move_backward(db):

    _, conv_repo, message_repo = db

    conv_repo.create_or_get(
        conv()
    )

    message_repo.create_with_attachments(
        message(
            "m1",
            at=NOW + timedelta(hours=1),
        ),
        (),
    )

    message_repo.create_with_attachments(
        message(
            "m2",
            at=NOW,
        ),
        (),
    )

    assert conv_repo.get_by_id(
        "c1"
    ).last_message_at == (
        NOW + timedelta(hours=1)
    )