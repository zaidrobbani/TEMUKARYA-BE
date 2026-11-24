import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.modules.notifications.domain.entities import Notification, NotificationType
from app.modules.notifications.infrastructure import realtime
from app.modules.notifications.infrastructure.realtime import NotificationHub, queue_after_commit
from app.modules.notifications.presentation.dependencies import (
    get_notification_hub,
    get_notification_socket_authenticator,
    get_unread_counter,
)
from app.modules.notifications.presentation.router import router

USERS = {"token-a": "user-a", "token-b": "user-b"}


def make(user_id: str, title: str = "Pesan baru dari Izah") -> Notification:
    return Notification(
        id=str(uuid4()),
        user_id=user_id,
        notification_type=NotificationType.NEW_MESSAGE.value,
        title=title,
        body="“Halo”",
        reference_type="CONVERSATION",
        reference_id=str(uuid4()),
        created_at=datetime(2026, 11, 23, 5, 0, tzinfo=UTC),
    )


@pytest.fixture
def setup():
    app = FastAPI()
    app.include_router(router)
    hub = NotificationHub()

    def authenticate(token):
        if token not in USERS:
            raise ValueError("token")
        return USERS[token]

    app.dependency_overrides.update({
        get_notification_socket_authenticator: lambda: authenticate,
        get_unread_counter: lambda: (lambda user_id: 3),
        get_notification_hub: lambda: hub,
    })
    with TestClient(app) as client:
        yield client, hub


def test_invalid_token_is_closed_with_4401(setup):
    client, _ = setup
    with client.websocket_connect("/notifications/ws?token=palsu") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401


def test_missing_token_is_closed_with_4401(setup):
    client, _ = setup
    with client.websocket_connect("/notifications/ws") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401


def test_ready_then_new_notification_is_pushed(setup):
    client, hub = setup
    with client.websocket_connect("/notifications/ws", headers={"Authorization": "Bearer token-a"}) as ws:
        assert ws.receive_json() == {"type": "ready", "unread_count": 3}
        notification = make("user-a")
        hub.publish(notification)
        event = ws.receive_json()
    assert event["type"] == "notification"
    body = event["notification"]
    assert body["id"] == notification.id
    assert body["title"] == "Pesan baru dari Izah"
    assert body["category"] == "MESSAGE"
    assert body["is_read"] is False
    assert body["reference_type"] == "CONVERSATION"


def test_notification_only_reaches_its_owner(setup):
    client, hub = setup
    with client.websocket_connect("/notifications/ws?token=token-a") as ws:
        ws.receive_json()
        hub.publish(make("user-b", "Untuk B"))
        hub.publish(make("user-a", "Untuk A"))
        assert ws.receive_json()["notification"]["title"] == "Untuk A"


def test_ping_pong_and_cleanup_on_disconnect(setup):
    client, hub = setup
    with client.websocket_connect("/notifications/ws?token=token-a") as ws:
        ws.receive_json()
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
        assert hub.connection_count("user-a") == 1
    # Server melepas koneksi secara asinkron setelah klien menutup socket.
    deadline = time.monotonic() + 2
    while hub.connection_count("user-a") and time.monotonic() < deadline:
        time.sleep(0.01)
    assert hub.connection_count("user-a") == 0


def test_publish_without_listener_is_noop():
    NotificationHub().publish(make("user-a"))


class RecordingHub:
    def __init__(self):
        self.published = []

    def publish(self, notification):
        self.published.append(notification)


@pytest.fixture
def recording(monkeypatch):
    hub = RecordingHub()
    monkeypatch.setattr(realtime, "notification_hub", hub)
    engine = create_engine("sqlite://")
    yield hub, engine
    engine.dispose()


def test_queued_notification_is_published_only_after_commit(recording):
    hub, engine = recording
    with Session(engine) as session:
        session.execute(text("SELECT 1"))
        notification = make("user-a")
        queue_after_commit(session, notification)
        assert hub.published == []
        session.commit()
    assert hub.published == [notification]


def test_rolled_back_notification_is_never_published(recording):
    hub, engine = recording
    with Session(engine) as session:
        session.execute(text("SELECT 1"))
        queue_after_commit(session, make("user-a"))
        session.rollback()
        session.execute(text("SELECT 1"))
        session.commit()
    assert hub.published == []
