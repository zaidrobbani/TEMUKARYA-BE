from dataclasses import replace
from datetime import timedelta

import pytest

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.modules.chat.application.dto import DeleteMessagesInput, ListMessagesInput
from app.modules.chat.application.use_cases import (
    DeleteMessages,
    ListConversationMessages,
    MessageDeleteExpiredError,
)
from app.modules.chat.domain.entities import MessageAttachment, MessageDeleteScope, MessageType
from app.modules.chat.presentation.dependencies import get_chat_attachment_storage
from app.modules.chat.presentation.realtime import get_chat_hub
from tests.modules.chat import test_repositories as repo_tests
from tests.modules.chat import test_router as router_tests
from tests.modules.chat.test_use_cases import (
    FREELANCER,
    NOW,
    OUTSIDER,
    UMKM,
    FakeChatRepository,
    make_message,
)

ME = MessageDeleteScope.ME
EVERYONE = MessageDeleteScope.EVERYONE


def attachment(message_id: str, key: str = "a1.webp") -> MessageAttachment:
    return MessageAttachment(
        id=f"att-{message_id}",
        message_id=message_id,
        original_file_name="foto.webp",
        storage_key=key,
        mime_type="image/webp",
        file_size_bytes=10,
        uploaded_at=NOW,
    )


@pytest.fixture
def repo():
    repo = FakeChatRepository()
    repo.messages = [
        make_message("m1", sender_id="u1"),
        make_message("m2", sender_id="u1", sent_at=NOW + timedelta(minutes=1)),
        make_message("m3", sender_id="f1", sent_at=NOW + timedelta(minutes=2)),
    ]
    return repo


def delete(repo, ids, scope, actor=UMKM, now=NOW + timedelta(hours=1), conversation_id="c1"):
    return DeleteMessages(repo, repo, clock=lambda: now).execute(
        DeleteMessagesInput(conversation_id=conversation_id, actor=actor, message_ids=tuple(ids), scope=scope)
    )


def history(repo, actor):
    page = ListConversationMessages(repo, repo).execute(ListMessagesInput(conversation_id="c1", actor=actor))
    return {item.message.id: item for item in page.items}


class TestDeleteForMe:
    def test_hides_only_for_actor(self, repo):
        result = delete(repo, ["m1", "m3"], ME)

        assert result.scope == ME
        assert result.message_ids == ("m1", "m3")
        assert set(history(repo, UMKM)) == {"m2"}
        assert set(history(repo, FREELANCER)) == {"m1", "m2", "m3"}

    def test_can_hide_counterpart_message(self, repo):
        delete(repo, ["m3"], ME)
        assert "m3" not in history(repo, UMKM)

    def test_is_idempotent_and_dedupes_ids(self, repo):
        delete(repo, ["m1"], ME)
        result = delete(repo, ["m1", "m1"], ME)
        assert result.message_ids == ("m1",)

    def test_keeps_message_content(self, repo):
        delete(repo, ["m1"], ME)
        assert history(repo, FREELANCER)["m1"].message.message_text == "Hello"


class TestDeleteForEveryone:
    def test_marks_deleted_for_both_participants(self, repo):
        repo.attachments = [attachment("m1")]
        result = delete(repo, ["m1"], EVERYONE)

        assert result.deleted_at == NOW + timedelta(hours=1)
        assert [a.storage_key for a in result.removed_attachments] == ["a1.webp"]
        for actor in (UMKM, FREELANCER):
            item = history(repo, actor)["m1"]
            assert item.message.deleted_at == result.deleted_at
            assert item.message.message_text is None
            assert item.attachments == ()

    def test_only_own_messages(self, repo):
        with pytest.raises(ForbiddenError, match="milik sendiri"):
            delete(repo, ["m1", "m3"], EVERYONE)
        assert history(repo, UMKM)["m1"].message.deleted_at is None

    def test_expired_after_48_hours(self, repo):
        with pytest.raises(MessageDeleteExpiredError) as exc:
            delete(repo, ["m1"], EVERYONE, now=NOW + timedelta(hours=48, seconds=1))
        assert exc.value.code == "MESSAGE_DELETE_EXPIRED"

    def test_exactly_48_hours_still_allowed(self, repo):
        delete(repo, ["m1"], EVERYONE, now=NOW + timedelta(hours=48))
        assert history(repo, UMKM)["m1"].message.deleted_at is not None

    def test_already_deleted_is_skipped(self, repo):
        delete(repo, ["m1"], EVERYONE)
        first = history(repo, UMKM)["m1"].message.deleted_at
        result = delete(repo, ["m1"], EVERYONE, now=NOW + timedelta(days=10))
        assert result.removed_attachments == ()
        assert history(repo, UMKM)["m1"].message.deleted_at == first

    def test_deleted_message_can_then_be_hidden_for_me(self, repo):
        delete(repo, ["m1"], EVERYONE)
        delete(repo, ["m1"], ME, actor=FREELANCER)
        assert "m1" not in history(repo, FREELANCER)
        assert "m1" in history(repo, UMKM)


class TestValidation:
    def test_outsider_gets_not_found(self, repo):
        with pytest.raises(NotFoundError, match="Percakapan"):
            delete(repo, ["m1"], ME, actor=OUTSIDER)

    def test_unknown_message(self, repo):
        with pytest.raises(NotFoundError, match="Pesan tidak ditemukan"):
            delete(repo, ["m1", "missing"], ME)
        assert set(history(repo, UMKM)) == {"m1", "m2", "m3"}

    def test_message_from_other_conversation(self, repo):
        repo.messages.append(replace(make_message("x1"), conversation_id="c2"))
        with pytest.raises(NotFoundError, match="Pesan tidak ditemukan"):
            delete(repo, ["x1"], ME)

    def test_empty_selection(self, repo):
        with pytest.raises(BadRequestError, match="minimal satu"):
            delete(repo, [], ME)

    def test_too_many(self, repo):
        with pytest.raises(BadRequestError, match="Maksimal 100"):
            delete(repo, [f"m{i}" for i in range(101)], ME)

    def test_blank_id(self, repo):
        with pytest.raises(BadRequestError):
            delete(repo, ["  "], ME)

    def test_invalid_scope(self, repo):
        with pytest.raises(BadRequestError, match="ME atau EVERYONE"):
            delete(repo, ["m1"], "ALL")


DELETE_URL = "/conversations/c1/messages/delete"


class FakeStorage:
    def __init__(self):
        self.deleted = []

    def delete(self, key):
        self.deleted.append(key)


class FakeHub:
    def __init__(self):
        self.events = []

    def broadcast_from_thread(self, conversation_id, event):
        self.events.append((conversation_id, event))


@pytest.fixture
def http(http_context):
    app, client, context = http_context
    storage, hub = FakeStorage(), FakeHub()
    app.dependency_overrides[get_chat_attachment_storage] = lambda: storage
    app.dependency_overrides[get_chat_hub] = lambda: hub
    recent = NOW.replace(year=NOW.year + 100)
    context.messages.messages = [
        replace(router_tests.make_message("m1", sender="u1"), sent_at=recent),
        replace(router_tests.make_message("m2", sender="f1", minute=1), sent_at=recent),
    ]
    context.messages.attachments = [attachment("m1", key="photo.webp")]
    return app, client, context, storage, hub


http_context = router_tests.http_context


def test_http_requires_login(http):
    _, client, *_ = http
    assert client.post(DELETE_URL, json={"message_ids": ["m1"], "scope": "ME"}).status_code == 401


def test_http_delete_for_me(http):
    app, client, context, storage, hub = http
    router_tests.authorize(app, router_tests.UMKM)

    response = client.post(DELETE_URL, json={"message_ids": ["m2"], "scope": "ME"})

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Pesan berhasil dihapus untuk saya"
    assert body["data"]["scope"] == "ME"
    assert body["data"]["message_ids"] == ["m2"]
    assert body["data"]["deleted_at"].endswith("Z")
    assert context.session.commits == 1
    assert hub.events == [] and storage.deleted == []

    ids = [i["message"]["id"] for i in client.get("/conversations/c1/messages").json()["data"]["items"]]
    assert ids == ["m1"]


def test_http_delete_for_everyone(http):
    app, client, context, storage, hub = http
    router_tests.authorize(app, router_tests.UMKM)

    response = client.post(DELETE_URL, json={"message_ids": ["m1"], "scope": "EVERYONE"})

    assert response.status_code == 200
    assert response.json()["message"] == "Pesan berhasil dihapus untuk semua orang"
    assert storage.deleted == ["photo.webp", "photo.thumb.webp"]
    conversation_id, event = hub.events[0]
    assert conversation_id == "c1"
    assert event["type"] == "message_deleted"
    assert event["message_ids"] == ["m1"]

    router_tests.authorize(app, router_tests.FREELANCER)
    items = client.get("/conversations/c1/messages").json()["data"]["items"]
    deleted = next(i for i in items if i["message"]["id"] == "m1")
    assert deleted["message"]["deleted_at"] is not None
    assert deleted["message"]["message_text"] is None
    assert deleted["attachments"] == []


def test_http_everyone_on_counterpart_message_forbidden(http):
    app, client, context, storage, hub = http
    router_tests.authorize(app, router_tests.UMKM)

    response = client.post(DELETE_URL, json={"message_ids": ["m1", "m2"], "scope": "EVERYONE"})

    assert response.status_code == 403
    assert response.json()["message"] == "Hanya pesan milik sendiri yang bisa dihapus untuk semua orang"
    assert context.session.rollbacks == 1
    assert storage.deleted == [] and hub.events == []


def test_http_expired_has_code(http):
    app, client, context, *_ = http
    router_tests.authorize(app, router_tests.UMKM)
    context.messages.messages = [router_tests.make_message("old", sender="u1")]

    response = client.post(DELETE_URL, json={"message_ids": ["old"], "scope": "EVERYONE"})

    assert response.status_code == 400
    assert response.json()["code"] == "MESSAGE_DELETE_EXPIRED"


def test_http_unknown_message(http):
    app, client, *_ = http
    router_tests.authorize(app, router_tests.UMKM)
    response = client.post(DELETE_URL, json={"message_ids": ["nope"], "scope": "ME"})
    assert response.status_code == 404
    assert response.json()["message"] == "Pesan tidak ditemukan"


def test_http_outsider(http):
    app, client, *_ = http
    router_tests.authorize(app, router_tests.OUTSIDER)
    response = client.post(DELETE_URL, json={"message_ids": ["m1"], "scope": "ME"})
    assert response.status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"message_ids": [], "scope": "ME"},
        {"message_ids": ["m1"], "scope": "ALL"},
        {"message_ids": ["m1"]},
        {"message_ids": [f"m{i}" for i in range(101)], "scope": "ME"},
    ],
)
def test_http_validation(http, body):
    app, client, *_ = http
    router_tests.authorize(app, router_tests.UMKM)
    response = client.post(DELETE_URL, json=body)
    assert response.status_code == 422
    assert response.json()["errors"]


db = repo_tests.db


def _seed(db):
    session, conv_repo, msg_repo = db
    conv_repo.create_or_get(repo_tests.conv())
    msg_repo.create_with_attachments(repo_tests.message("m1"), ())
    photo = replace(attachment("m2"), message_id="m2")
    m2 = replace(repo_tests.message("m2", at=NOW + timedelta(minutes=1)), message_type=MessageType.IMAGE)
    msg_repo.create_with_attachments(m2, (photo,))
    msg_repo.create_with_attachments(repo_tests.message("m3", sender="f1", at=NOW + timedelta(minutes=2)), ())
    session.flush()
    return session, msg_repo


def test_repository_hide_for_user(db):
    session, msg_repo = _seed(db)

    msg_repo.hide_for_user(("m1", "m3"), "u1", NOW)
    msg_repo.hide_for_user(("m1",), "u1", NOW)

    seen_by_umkm = [m.id for m in msg_repo.list_for_conversation("c1", limit=10, viewer_user_id="u1")]
    seen_by_freelancer = [m.id for m in msg_repo.list_for_conversation("c1", limit=10, viewer_user_id="f1")]
    assert seen_by_umkm == ["m2"]
    assert seen_by_freelancer == ["m3", "m2", "m1"]


def test_repository_delete_for_everyone(db):
    session, msg_repo = _seed(db)

    removed = msg_repo.delete_for_everyone(("m1", "m2"), NOW + timedelta(hours=1))

    assert [a.id for a in removed] == ["att-m2"]
    assert msg_repo.list_attachments(("m2",)) == ()
    messages = {m.id: m for m in msg_repo.list_by_ids("c1", ("m1", "m2", "m3"))}
    assert messages["m1"].message_text is None
    assert messages["m1"].deleted_at == NOW + timedelta(hours=1)
    assert messages["m2"].deleted_at is not None
    assert messages["m3"].deleted_at is None


def test_repository_list_by_ids_scoped_to_conversation(db):
    _, msg_repo = _seed(db)
    assert {m.id for m in msg_repo.list_by_ids("c1", ("m1", "missing"))} == {"m1"}
    assert msg_repo.list_by_ids("other", ("m1",)) == ()
    assert msg_repo.list_by_ids("c1", ()) == ()
