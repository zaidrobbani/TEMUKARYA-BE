from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_handlers import register_error_handlers

from app.modules.chat.domain.entities import (
    ChatActor,
    Conversation,
    Message,
    MessageAttachment,
    MessageType,
)

from app.modules.chat.presentation.dependencies import (
    get_authenticated_chat_actor,
    get_chat_database_context,
    get_new_message_hook,
)

from app.modules.chat.presentation.router import router


# ============================================================
# 1. CONSTANTS
# ============================================================

NOW = datetime(
    2026, 11, 4, 10, 0,
    tzinfo=timezone.utc,
)

UMKM = ChatActor("u1", "UMKM")
FREELANCER = ChatActor("f1", "FREELANCER")
OUTSIDER = ChatActor("u2", "UMKM")

BASE_URL = "/conversations"
DETAIL_URL = "/conversations/c1"
MESSAGES_URL = "/conversations/c1/messages"
READ_URL = "/conversations/c1/read"


# ============================================================
# 2. FAKE SESSION
# ============================================================

class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.fail_commit = False

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("Simulated commit failure")

        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


# ============================================================
# 3. FAKE CONVERSATION REPOSITORY
# ============================================================

class FakeConversationRepository:

    def __init__(self):
        self.conversations = {
            "c1": Conversation(
                id="c1",
                umkm_id="u1",
                freelancer_id="f1",
                project_id=None,
                last_message_at=None,
                created_at=NOW,
                updated_at=NOW,
            ),
        }

        self.roles = {
            "u1": "UMKM",
            "u2": "UMKM",
            "f1": "FREELANCER",
            "f2": "FREELANCER",
        }

        self.project_owners = {
            "p1": "u1",
            "p2": "u2",
        }

    def get_user_role(self, user_id):
        return self.roles.get(user_id)

    def get_project_owner_id(self, project_id):
        return self.project_owners.get(project_id)

    def get_by_id(self, conversation_id):
        return self.conversations.get(conversation_id)

    def find_by_participants(
        self,
        umkm_id,
        freelancer_id,
        project_id,
    ):
        for item in self.conversations.values():
            if (
                item.umkm_id == umkm_id
                and item.freelancer_id == freelancer_id
                and item.project_id == project_id
            ):
                return item

        return None

    def create_or_get(self, conversation):
        existing = self.find_by_participants(
            conversation.umkm_id,
            conversation.freelancer_id,
            conversation.project_id,
        )

        if existing is not None:
            return existing

        self.conversations[
            conversation.id
        ] = conversation

        return conversation

    def list_for_user(
        self,
        user_id,
        *,
        limit,
        offset,
    ):
        items = [
            item
            for item in self.conversations.values()
            if user_id in (
                item.umkm_id,
                item.freelancer_id,
            )
        ]

        items.sort(
            key=lambda item: (
                item.last_message_at or item.created_at,
                item.id,
            ),
            reverse=True,
        )

        return tuple(
            items[offset:offset + limit]
        )


# ============================================================
# 4. FAKE MESSAGE REPOSITORY
# ============================================================

class FakeMessageRepository:

    def __init__(
        self,
        conversation_repository,
    ):
        self.conversations = conversation_repository
        self.messages = []
        self.attachments = []

    def create_with_attachments(
        self,
        message,
        attachments,
    ):
        conversation = self.conversations.get_by_id(
            message.conversation_id
        )

        assert conversation is not None

        self.messages.append(message)
        self.attachments.extend(attachments)

        self.conversations.conversations[
            conversation.id
        ] = replace(
            conversation,
            last_message_at=message.sent_at,
            updated_at=message.sent_at,
        )

        return message

    def list_for_conversation(
        self,
        conversation_id,
        *,
        limit,
        before=None,
    ):
        items = [
            item
            for item in self.messages
            if item.conversation_id == conversation_id
        ]

        items.sort(
            key=lambda item: (
                item.sent_at,
                item.id,
            ),
            reverse=True,
        )

        if before is not None:
            items = [
                item
                for item in items
                if (
                    item.sent_at,
                    item.id,
                ) < before
            ]

        return tuple(items[:limit])

    def list_attachments(
        self,
        message_ids,
    ):
        return tuple(
            item
            for item in self.attachments
            if item.message_id in message_ids
        )

    def get_by_id(self, message_id):
        return next(
            (
                item
                for item in self.messages
                if item.id == message_id
            ),
            None,
        )

    def mark_received_messages_read(
        self,
        conversation_id,
        recipient_user_id,
        read_at,
    ):
        conversation = self.conversations.get_by_id(
            conversation_id
        )

        if conversation is None:
            return 0

        allowed = {
            conversation.umkm_id,
            conversation.freelancer_id,
        }

        updated = 0

        for index, message in enumerate(self.messages):
            if (
                message.conversation_id == conversation_id
                and message.sender_user_id in allowed
                and message.sender_user_id
                != recipient_user_id
                and message.read_at is None
            ):
                self.messages[index] = replace(
                    message,
                    read_at=read_at,
                )

                updated += 1

        return updated


# ============================================================
# 5. FAKE DATABASE CONTEXT
# ============================================================

@dataclass
class FakeChatContext:
    session: FakeSession
    conversations: FakeConversationRepository
    messages: FakeMessageRepository


# ============================================================
# 6. HTTP FIXTURE
# ============================================================

@pytest.fixture
def http_context():
    app = FastAPI()

    register_error_handlers(app)
    app.include_router(router)

    conversations = FakeConversationRepository()

    messages = FakeMessageRepository(
        conversations
    )

    context = FakeChatContext(
        session=FakeSession(),
        conversations=conversations,
        messages=messages,
    )

    app.dependency_overrides[
        get_chat_database_context
    ] = lambda: context

    app.dependency_overrides[
        get_new_message_hook
    ] = lambda: lambda *args: None

    with TestClient(app) as client:
        yield app, client, context

    app.dependency_overrides.clear()


def authorize(app, actor):
    """
    Override authentication hanya untuk test.
    """

    app.dependency_overrides[
        get_authenticated_chat_actor
    ] = lambda: actor


def make_message(
    message_id,
    sender="u1",
    minute=0,
    message_type=MessageType.TEXT,
    message_text="Hello",
):
    at = NOW + timedelta(minutes=minute)

    return Message(
        id=message_id,
        conversation_id="c1",
        sender_user_id=sender,
        message_text=message_text,
        message_type=message_type,
        sent_at=at,
        created_at=at,
    )


# ============================================================
# 7. AUTHENTICATION TESTS
# ============================================================

@pytest.mark.parametrize(
    "method,url,body",
    [
        ("GET", BASE_URL, None),
        (
            "POST",
            BASE_URL,
            {"counterpart_user_id": "f1"},
        ),
        ("GET", DETAIL_URL, None),
        (
            "POST",
            MESSAGES_URL,
            {"message_text": "Hello"},
        ),
        ("GET", MESSAGES_URL, None),
        ("PATCH", READ_URL, None),
    ],
)
def test_unauthenticated_returns_401(
    http_context,
    method,
    url,
    body,
):
    _, client, _ = http_context

    response = client.request(
        method,
        url,
        json=body,
    )

    assert response.status_code == 401


def test_fake_bearer_token_rejected(http_context):
    _, client, _ = http_context

    response = client.get(
        BASE_URL,
        headers={
            "Authorization": "Bearer fake-token"
        },
    )

    assert response.status_code == 401


def test_invalid_role_rejected(http_context):
    app, client, _ = http_context

    authorize(
        app,
        ChatActor("admin1", "ADMIN"),
    )

    response = client.get(BASE_URL)

    assert response.status_code == 403


# ============================================================
# 8. CONVERSATION LIST + DETAIL
# ============================================================

def test_umkm_get_own_conversations(http_context):
    app, client, _ = http_context

    authorize(app, UMKM)

    response = client.get(BASE_URL)

    assert response.status_code == 200

    body = response.json()["data"]

    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "c1"
    assert body["limit"] == 20
    assert body["offset"] == 0


def test_freelancer_get_own_conversation(
    http_context,
):
    app, client, _ = http_context

    authorize(app, FREELANCER)

    response = client.get(DETAIL_URL)

    assert response.status_code == 200
    assert response.json()["data"]["freelancer_id"] == "f1"


def test_outsider_list_is_empty(http_context):
    app, client, _ = http_context

    authorize(app, OUTSIDER)

    response = client.get(BASE_URL)

    assert response.status_code == 200
    assert response.json()["data"]["items"] == []


def test_outsider_cannot_read_detail(
    http_context,
):
    app, client, _ = http_context

    authorize(app, OUTSIDER)

    response = client.get(DETAIL_URL)

    assert response.status_code == 404


def test_missing_conversation_returns_404(
    http_context,
):
    app, client, _ = http_context

    authorize(app, UMKM)

    response = client.get(
        "/conversations/missing"
    )

    assert response.status_code == 404


def test_invalid_list_limit_returns_422(
    http_context,
):
    app, client, _ = http_context

    authorize(app, UMKM)

    response = client.get(
        "/conversations?limit=101"
    )

    assert response.status_code == 422


# ============================================================
# 9. CREATE CONVERSATION
# ============================================================

def test_create_conversation_and_commit(
    http_context,
):
    app, client, context = http_context

    authorize(app, UMKM)

    response = client.post(
        BASE_URL,
        json={
            "counterpart_user_id": "f2",
        },
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert body["umkm_id"] == "u1"
    assert body["freelancer_id"] == "f2"
    assert body["project_id"] is None

    assert context.session.commits == 1


def test_existing_conversation_is_reused(
    http_context,
):
    app, client, context = http_context

    authorize(app, UMKM)

    response = client.post(
        BASE_URL,
        json={
            "counterpart_user_id": "f1",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "c1"

    assert len(context.conversations.conversations) == 1
    assert context.session.commits == 1


def test_create_project_conversation(
    http_context,
):
    app, client, _ = http_context

    authorize(app, UMKM)

    response = client.post(
        BASE_URL,
        json={
            "counterpart_user_id": "f2",
            "project_id": "p1",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["project_id"] == "p1"


def test_project_owner_mismatch_rejected(
    http_context,
):
    app, client, context = http_context

    authorize(app, UMKM)

    response = client.post(
        BASE_URL,
        json={
            "counterpart_user_id": "f1",
            "project_id": "p2",
        },
    )

    assert response.status_code == 404
    assert context.session.rollbacks == 1


def test_invalid_counterpart_rejected(
    http_context,
):
    app, client, context = http_context

    authorize(app, UMKM)

    response = client.post(
        BASE_URL,
        json={
            "counterpart_user_id": "unknown",
        },
    )

    assert response.status_code == 404
    assert context.session.commits == 0


# ============================================================
# 10. SEND MESSAGE
# ============================================================

def test_umkm_sends_text_and_commits(
    http_context,
):
    app, client, context = http_context

    authorize(app, UMKM)

    response = client.post(
        MESSAGES_URL,
        json={
            "message_text": "  Halo Freelancer!  ",
        },
    )

    assert response.status_code == 201

    body = response.json()["data"]

    assert body["sender_user_id"] == "u1"
    assert body["message_text"] == (
        "Halo Freelancer!"
    )
    assert body["message_type"] == "TEXT"

    assert context.session.commits == 1
    assert len(context.messages.messages) == 1

    assert (
        context.conversations
        .get_by_id("c1")
        .last_message_at
        is not None
    )


def test_freelancer_can_send_reply(
    http_context,
):
    app, client, _ = http_context

    authorize(app, FREELANCER)

    response = client.post(
        MESSAGES_URL,
        json={
            "message_text": "Siap, Kak!",
        },
    )

    assert response.status_code == 201

    assert response.json()["data"]["sender_user_id"] == "f1"


def test_empty_message_returns_400_and_rolls_back(
    http_context,
):
    app, client, context = http_context

    authorize(app, UMKM)

    response = client.post(
        MESSAGES_URL,
        json={
            "message_text": "    ",
        },
    )

    assert response.status_code == 400

    assert context.session.commits == 0
    assert context.session.rollbacks == 1


def test_outsider_cannot_send_message(
    http_context,
):
    app, client, context = http_context

    authorize(app, OUTSIDER)

    response = client.post(
        MESSAGES_URL,
        json={
            "message_text": "Forged message",
        },
    )

    assert response.status_code == 404
    assert context.session.commits == 0
    assert context.session.rollbacks == 1


def test_sender_identity_cannot_be_overridden(
    http_context,
):
    app, client, _ = http_context

    authorize(app, UMKM)

    response = client.post(
        MESSAGES_URL,
        json={
            "message_text": "Hello",
            "sender_user_id": "u2",
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["sender_user_id"] == "u1"


# ============================================================
# 11. MESSAGE HISTORY + PAGINATION
# ============================================================

def test_message_history_sorted_descending(
    http_context,
):
    app, client, context = http_context

    authorize(app, UMKM)

    context.messages.messages = [
        make_message("m1", minute=1),
        make_message(
            "m2",
            sender="f1",
            minute=2,
        ),
    ]

    response = client.get(MESSAGES_URL)

    assert response.status_code == 200

    assert [
        item["message"]["id"]
        for item in response.json()["data"]["items"]
    ] == ["m2", "m1"]


def test_message_history_keyset_pagination(
    http_context,
):
    app, client, context = http_context

    authorize(app, UMKM)

    context.messages.messages = [
        make_message("m1", minute=1),
        make_message("m2", minute=2),
    ]

    first = client.get(
        MESSAGES_URL,
        params={
            "limit": 1,
        },
    )

    assert first.status_code == 200

    body = first.json()["data"]

    assert body["has_more"] is True

    cursor = body["next_before"]

    assert cursor is not None

    second = client.get(
        MESSAGES_URL,
        params={
            "limit": 1,
            "before_at": cursor["sent_at"],
            "before_id": cursor["message_id"],
        },
    )

    assert second.status_code == 200

    assert [
        item["message"]["id"]
        for item in second.json()["data"]["items"]
    ] == ["m1"]

    assert second.json()["data"]["has_more"] is False


def test_partial_cursor_returns_400(
    http_context,
):
    app, client, _ = http_context

    authorize(app, UMKM)

    response = client.get(
        MESSAGES_URL,
        params={
            "before_id": "m2",
        },
    )

    assert response.status_code == 400


def test_naive_cursor_returns_400(
    http_context,
):
    app, client, _ = http_context

    authorize(app, UMKM)

    response = client.get(
        MESSAGES_URL,
        params={
            "before_at": "2026-11-04T10:02:00",
            "before_id": "m2",
        },
    )

    assert response.status_code == 400


def test_message_history_excludes_storage_key(
    http_context,
):
    app, client, context = http_context

    authorize(app, UMKM)

    context.messages.messages = [
        make_message(
            "m1",
            message_type=MessageType.FILE,
            message_text=None,
        ),
    ]

    context.messages.attachments = [
        MessageAttachment(
            id="a1",
            message_id="m1",
            original_file_name="brief.pdf",
            storage_key="chat/m1/secret.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            uploaded_at=NOW,
        ),
    ]

    response = client.get(MESSAGES_URL)

    assert response.status_code == 200

    attachment = response.json()["data"][
        "items"
    ][0]["attachments"][0]

    assert attachment["id"] == "a1"
    assert attachment["mime_type"] == "application/pdf"

    assert "storage_key" not in attachment


def test_outsider_cannot_read_history(
    http_context,
):
    app, client, _ = http_context

    authorize(app, OUTSIDER)

    response = client.get(MESSAGES_URL)

    assert response.status_code == 404


# ============================================================
# 12. MARK AS READ
# ============================================================

def test_mark_received_message_read_and_commit(
    http_context,
):
    app, client, context = http_context

    authorize(app, UMKM)

    context.messages.messages = [
        make_message("m1", sender="u1"),
        make_message("m2", sender="f1"),
    ]

    response = client.patch(READ_URL)

    assert response.status_code == 200
    assert response.json()["data"]["marked_count"] == 1

    assert context.messages.messages[0].read_at is None
    assert context.messages.messages[1].read_at is not None

    assert context.session.commits == 1


def test_mark_read_is_idempotent(
    http_context,
):
    app, client, context = http_context

    authorize(app, UMKM)

    context.messages.messages = [
        make_message("m1", sender="f1"),
    ]

    first = client.patch(READ_URL)
    second = client.patch(READ_URL)

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.json()["data"]["marked_count"] == 1
    assert second.json()["data"]["marked_count"] == 0

    assert context.session.commits == 2


def test_outsider_cannot_mark_read(
    http_context,
):
    app, client, context = http_context

    authorize(app, OUTSIDER)

    response = client.patch(READ_URL)

    assert response.status_code == 404
    assert context.session.rollbacks == 1


def test_commit_failure_calls_rollback(
    http_context,
):
    app, client, context = http_context

    authorize(app, UMKM)

    context.session.fail_commit = True

    with pytest.raises(RuntimeError):
        client.post(
            MESSAGES_URL,
            json={
                "message_text": "Hello",
            },
        )

    assert context.session.rollbacks == 1


# ============================================================
# 13. OPENAPI CONTRACT
# ============================================================

def test_openapi_chat_routes(http_context):
    app, _, _ = http_context

    paths = app.openapi()["paths"]

    assert set(paths[BASE_URL]) == {
        "get", "post"
    }

    assert set(
        paths["/conversations/{conversation_id}"]
    ) == {"get"}

    assert set(
        paths["/conversations/{conversation_id}/messages"]
    ) == {"get", "post"}

    assert set(
        paths["/conversations/{conversation_id}/read"]
    ) == {"patch"}


def test_main_app_registers_chat_router():
    from app.main import app

    paths = app.openapi()["paths"]

    assert "/api/v1/conversations" in paths

    assert (
        "/api/v1/conversations/{conversation_id}/messages"
        in paths
    )

    assert (
        "/api/v1/conversations/{conversation_id}/read"
        in paths
    )