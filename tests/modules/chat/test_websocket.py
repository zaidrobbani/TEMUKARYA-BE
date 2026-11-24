from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.error_handlers import register_error_handlers
from app.core.exceptions import UnauthorizedError
from app.modules.chat.presentation.dependencies import (
    get_authenticated_chat_actor,
    get_chat_database_context,
    get_new_message_hook,
)
from app.modules.chat.presentation.realtime import (
    CLOSE_NOT_FOUND,
    CLOSE_UNAUTHORIZED,
    ChatHub,
    get_chat_context_factory,
    get_chat_hub,
    get_socket_authenticator,
    get_socket_message_notifier,
)
from app.modules.chat.presentation.router import router
from tests.modules.chat.test_router import (
    FREELANCER,
    OUTSIDER,
    UMKM,
    FakeChatContext,
    FakeConversationRepository,
    FakeMessageRepository,
    FakeSession,
)

TOKENS = {"token-umkm": UMKM, "token-freelancer": FREELANCER, "token-outsider": OUTSIDER}
WS_URL = "/conversations/c1/ws"


@pytest.fixture
def chat():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)

    conversations = FakeConversationRepository()
    context = FakeChatContext(FakeSession(), conversations, FakeMessageRepository(conversations))
    hub = ChatHub()
    notified: list[tuple] = []

    @contextmanager
    def open_context():
        yield context

    def authenticate(token):
        if token not in TOKENS:
            raise UnauthorizedError("Token tidak valid")
        return TOKENS[token]

    app.dependency_overrides.update({
        get_chat_context_factory: lambda: open_context,
        get_socket_authenticator: lambda: authenticate,
        get_socket_message_notifier: lambda: lambda *args: notified.append(args[1:]),
        get_chat_hub: lambda: hub,
        get_chat_database_context: lambda: context,
        get_new_message_hook: lambda: lambda *args: None,
    })
    with TestClient(app) as client:
        yield client, app, context, hub, notified
    app.dependency_overrides.clear()


def connect(client, token="token-umkm", via_header=True):
    if via_header:
        return client.websocket_connect(WS_URL, headers={"Authorization": f"Bearer {token}"})
    return client.websocket_connect(f"{WS_URL}?token={token}")


class TestHandshake:
    def test_ready_event_after_connect(self, chat):
        client, *_ = chat
        with connect(client) as ws:
            assert ws.receive_json() == {"type": "ready", "conversation_id": "c1"}

    def test_query_token_is_accepted(self, chat):
        client, *_ = chat
        with connect(client, "token-freelancer", via_header=False) as ws:
            assert ws.receive_json()["type"] == "ready"

    @pytest.mark.parametrize("token", [None, "palsu"])
    def test_missing_or_invalid_token_closes_4401(self, chat, token):
        client, *_ = chat
        url = WS_URL if token is None else f"{WS_URL}?token={token}"
        with pytest.raises(WebSocketDisconnect) as closed:
            with client.websocket_connect(url) as ws:
                ws.receive_json()
        assert closed.value.code == CLOSE_UNAUTHORIZED

    def test_outsider_closes_4404(self, chat):
        client, *_ = chat
        with pytest.raises(WebSocketDisconnect) as closed:
            with connect(client, "token-outsider") as ws:
                ws.receive_json()
        assert closed.value.code == CLOSE_NOT_FOUND

    def test_unknown_conversation_closes_4404(self, chat):
        client, *_ = chat
        with pytest.raises(WebSocketDisconnect) as closed:
            with client.websocket_connect("/conversations/tidak-ada/ws?token=token-umkm") as ws:
                ws.receive_json()
        assert closed.value.code == CLOSE_NOT_FOUND


class TestRealtimeMessages:
    def test_message_is_broadcast_to_both_participants(self, chat):
        client, _, context, _, notified = chat
        with connect(client, "token-umkm") as umkm, connect(client, "token-freelancer") as freelancer:
            umkm.receive_json()
            freelancer.receive_json()

            umkm.send_json({"type": "message", "text": "  Halo, desainnya sudah oke  "})

            to_sender = umkm.receive_json()
            to_receiver = freelancer.receive_json()
        assert to_sender == to_receiver
        assert to_receiver["type"] == "message"
        message = to_receiver["message"]
        assert message["sender_user_id"] == "u1"
        assert message["conversation_id"] == "c1"
        assert message["message_text"] == "Halo, desainnya sudah oke"
        assert message["sent_at"].endswith("Z")
        assert context.session.commits == 1
        assert notified == [("c1", "u1", "Halo, desainnya sudah oke")]

    def test_empty_message_returns_error_and_keeps_connection(self, chat):
        client, _, context, *_ = chat
        with connect(client) as ws:
            ws.receive_json()
            ws.send_json({"type": "message", "text": "   "})
            error = ws.receive_json()
            ws.send_json({"type": "ping"})
            assert ws.receive_json() == {"type": "pong"}
        assert error["type"] == "error" and error["message"]
        assert context.session.commits == 0

    @pytest.mark.parametrize("payload", ['{"type":"message","text":5}', "bukan json", '{"type":"lain"}', "[1,2]"])
    def test_malformed_events_return_error(self, chat, payload):
        client, *_ = chat
        with connect(client) as ws:
            ws.receive_json()
            ws.send_text(payload)
            assert ws.receive_json()["type"] == "error"

    def test_rest_send_is_pushed_to_socket(self, chat):
        client, app, *_ = chat
        app.dependency_overrides[get_authenticated_chat_actor] = lambda: FREELANCER
        with connect(client, "token-umkm") as umkm:
            umkm.receive_json()

            response = client.post("/conversations/c1/messages", json={"message_text": "Dari REST"})

            pushed = umkm.receive_json()
        assert response.status_code == 201
        assert pushed["type"] == "message"
        assert pushed["message"]["message_text"] == "Dari REST"
        assert pushed["message"]["sender_user_id"] == "f1"


class TestReadReceipts:
    def test_read_event_marks_incoming_and_broadcasts(self, chat):
        client, *_ = chat
        with connect(client, "token-umkm") as umkm, connect(client, "token-freelancer") as freelancer:
            umkm.receive_json()
            freelancer.receive_json()
            umkm.send_json({"type": "message", "text": "Cek draf ya"})
            umkm.receive_json()
            freelancer.receive_json()

            freelancer.send_json({"type": "read"})

            seen_by_umkm = umkm.receive_json()
            seen_by_freelancer = freelancer.receive_json()
        assert seen_by_umkm == seen_by_freelancer
        assert seen_by_umkm["type"] == "read"
        assert seen_by_umkm["reader_user_id"] == "f1"
        assert seen_by_umkm["marked_count"] == 1
        assert seen_by_umkm["read_at"].endswith("Z")


class TestHub:
    def test_disconnect_removes_socket_from_room(self, chat):
        client, _, _, hub, _ = chat
        with connect(client) as ws:
            ws.receive_json()
            assert hub.connection_count("c1") == 1
        # Keluar dari context = socket ditutup client.
        with connect(client, "token-freelancer") as ws:
            ws.receive_json()
            ws.send_json({"type": "ping"})
            ws.receive_json()
            assert hub.connection_count("c1") == 1
