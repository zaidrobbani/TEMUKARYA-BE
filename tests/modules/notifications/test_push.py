import json
import time
from datetime import UTC, datetime
from unittest.mock import MagicMock
from urllib.parse import parse_qs

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_uow
from app.core.error_handlers import register_error_handlers
from app.core.unit_of_work import UnitOfWork
from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.notifications.domain.entities import Notification, NotificationType
from app.modules.notifications.infrastructure.device_tokens import SqlAlchemyDeviceTokenRepository
from app.modules.notifications.infrastructure.push import (
    FcmClient,
    PushDispatcher,
    SendResult,
    ServiceAccount,
    build_dispatcher,
    notification_data,
)
from app.modules.notifications.presentation.dependencies import get_device_token_repository
from app.modules.notifications.presentation.router import router

TOKEN_A = "fcm-token-perangkat-a-1234567890"
TOKEN_B = "fcm-token-perangkat-b-1234567890"


@pytest.fixture(scope="module")
def private_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    ).decode()
    return key, pem


@pytest.fixture
def account(private_key):
    return ServiceAccount(
        project_id="temukarya-uji",
        client_email="push@temukarya-uji.iam.gserviceaccount.com",
        private_key=private_key[1],
        private_key_id="kid-1",
        token_uri="https://oauth2.googleapis.com/token",
    )


def notification(user_id="user-a") -> Notification:
    return Notification(
        id="n-1",
        user_id=user_id,
        notification_type=NotificationType.NEW_MESSAGE.value,
        title="Pesan baru dari Izah",
        body="“Halo”",
        reference_type="CONVERSATION",
        reference_id="c-1",
        created_at=datetime(2026, 11, 23, 5, 0, tzinfo=UTC),
    )


class FakeGoogle:
    """Server OAuth + FCM palsu; `fcm_status` menentukan jawaban per token."""

    def __init__(self, private_key):
        self.public_key = private_key[0].public_key()
        self.token_requests = 0
        self.sent: list[dict] = []
        self.fcm_status: dict[str, tuple[int, dict]] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            self.token_requests += 1
            form = parse_qs(request.content.decode())
            assert form["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]
            claims = jwt.decode(
                form["assertion"][0], self.public_key, algorithms=["RS256"],
                audience="https://oauth2.googleapis.com/token",
                options={"verify_exp": False, "verify_iat": False},  # jam test bisa digeser maju
            )
            assert claims["scope"] == "https://www.googleapis.com/auth/firebase.messaging"
            assert jwt.get_unverified_header(form["assertion"][0])["kid"] == "kid-1"
            return httpx.Response(200, json={"access_token": f"akses-{self.token_requests}", "expires_in": 3600})
        assert request.url.path == "/v1/projects/temukarya-uji/messages:send"
        body = json.loads(request.content)
        self.sent.append({"auth": request.headers["authorization"], **body["message"]})
        status, payload = self.fcm_status.get(body["message"]["token"], (200, {"name": "ok"}))
        return httpx.Response(status, json=payload)


@pytest.fixture
def google(private_key):
    return FakeGoogle(private_key)


@pytest.fixture
def client_for(account, google):
    def make(clock=time.time):
        return FcmClient(account, httpx.Client(transport=httpx.MockTransport(google.handler)), clock=clock)
    return make


UNREGISTERED = (404, {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}})


def test_send_uses_cached_access_token_and_high_priority_data_message(client_for, google):
    fcm = client_for()
    data = notification_data(notification())
    assert fcm.send(TOKEN_A, data) is SendResult.SENT
    assert fcm.send(TOKEN_B, data) is SendResult.SENT
    assert google.token_requests == 1
    first = google.sent[0]
    assert first["auth"] == "Bearer akses-1"
    assert first["token"] == TOKEN_A
    assert first["android"]["priority"] == "HIGH"
    assert first["data"] == {
        "notification_id": "n-1", "type": "NEW_MESSAGE", "category": "MESSAGE",
        "title": "Pesan baru dari Izah", "body": "“Halo”",
        "reference_type": "CONVERSATION", "reference_id": "c-1",
    }
    assert all(isinstance(value, str) for value in first["data"].values())
    assert "notification" not in first  # data message: aplikasi yang menampilkan


def test_access_token_refreshed_near_expiry(client_for, google):
    now = [time.time()]
    fcm = client_for(clock=lambda: now[0])
    fcm.send(TOKEN_A, {})
    now[0] += 3600 - 200  # dalam margin refresh 5 menit
    fcm.send(TOKEN_A, {})
    assert google.token_requests == 2
    assert google.sent[-1]["auth"] == "Bearer akses-2"


@pytest.mark.parametrize("response,expected", [
    (UNREGISTERED, SendResult.INVALID_TOKEN),
    ((400, {"error": {"status": "INVALID_ARGUMENT", "details": [{"errorCode": "INVALID_ARGUMENT"}]}}),
     SendResult.INVALID_TOKEN),
    ((500, {"error": {"status": "INTERNAL"}}), SendResult.FAILED),
    ((429, {"error": {"status": "RESOURCE_EXHAUSTED"}}), SendResult.FAILED),
])
def test_fcm_error_mapping(client_for, google, response, expected):
    google.fcm_status[TOKEN_A] = response
    assert client_for().send(TOKEN_A, {}) is expected


def test_auth_error_forces_new_access_token(client_for, google):
    fcm = client_for()
    google.fcm_status[TOKEN_A] = (401, {"error": {"status": "UNAUTHENTICATED"}})
    assert fcm.send(TOKEN_A, {}) is SendResult.FAILED
    google.fcm_status.clear()
    assert fcm.send(TOKEN_A, {}) is SendResult.SENT
    assert google.token_requests == 2


def test_oauth_failure_is_reported_not_raised(account):
    def handler(request):
        return httpx.Response(400, json={"error": "invalid_grant"})
    fcm = FcmClient(account, httpx.Client(transport=httpx.MockTransport(handler)))
    assert fcm.send(TOKEN_A, {}) is SendResult.FAILED


class FakeTokens:
    def __init__(self, tokens):
        self.tokens = {"user-a": list(tokens)}
        self.removed: list[str] = []

    def tokens_for(self, user_id):
        return list(self.tokens.get(user_id, []))

    def remove_tokens(self, tokens):
        self.removed.extend(tokens)


class InlineExecutor:
    def submit(self, fn, *args):
        fn(*args)


def test_dispatcher_sends_to_every_device_and_prunes_dead_tokens(client_for, google):
    google.fcm_status[TOKEN_B] = UNREGISTERED
    tokens = FakeTokens([TOKEN_A, TOKEN_B])
    session = MagicMock(spec=Session)
    dispatcher = PushDispatcher(
        client_for(), lambda: session, executor=InlineExecutor(), repository_factory=lambda _: tokens,
    )
    dispatcher.dispatch(notification())
    assert [message["token"] for message in google.sent] == [TOKEN_A, TOKEN_B]
    assert tokens.removed == [TOKEN_B]
    session.commit.assert_called_once()
    session.close.assert_called_once()


def test_dispatcher_without_devices_or_credentials_does_nothing(client_for, google):
    session = MagicMock(spec=Session)
    PushDispatcher(client_for(), lambda: session, executor=InlineExecutor(),
                   repository_factory=lambda _: FakeTokens([])).dispatch(notification("user-tanpa-hp"))
    assert google.sent == [] and google.token_requests == 0
    session.commit.assert_not_called()

    factory = MagicMock()
    disabled = PushDispatcher(None, factory, executor=InlineExecutor())
    disabled.dispatch(notification())
    assert disabled.enabled is False
    factory.assert_not_called()


def test_build_dispatcher_disabled_for_empty_missing_or_wrong_file(tmp_path):
    assert build_dispatcher("", MagicMock()).enabled is False
    assert build_dispatcher(str(tmp_path / "tidak-ada.json"), MagicMock()).enabled is False
    wrong = tmp_path / "google-services.json"
    wrong.write_text(json.dumps({"project_info": {"project_id": "x"}}))
    assert build_dispatcher(str(wrong), MagicMock()).enabled is False


def test_build_dispatcher_enabled_with_service_account(tmp_path, private_key):
    path = tmp_path / "firebase.json"
    path.write_text(json.dumps({
        "type": "service_account", "project_id": "temukarya-uji", "private_key_id": "kid-1",
        "private_key": private_key[1], "client_email": "push@temukarya-uji.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }))
    assert build_dispatcher(str(path), MagicMock()).enabled is True


# ------------------------------------------------------------
# Repository + endpoint token perangkat
# ------------------------------------------------------------

@pytest.fixture
def token_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE device_tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                platform TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """))
    session = Session(engine)
    yield session
    session.close()


def test_repository_upsert_moves_token_between_accounts(token_session):
    repository = SqlAlchemyDeviceTokenRepository(token_session)
    repository.upsert("user-a", TOKEN_A, "ANDROID")
    repository.upsert("user-a", TOKEN_A, "ANDROID")
    repository.upsert("user-a", TOKEN_B, "ANDROID")
    token_session.commit()
    assert sorted(repository.tokens_for("user-a")) == [TOKEN_A, TOKEN_B]
    repository.upsert("user-b", TOKEN_A, "ANDROID")  # HP yang sama login akun lain
    token_session.commit()
    assert repository.tokens_for("user-a") == [TOKEN_B]
    assert repository.tokens_for("user-b") == [TOKEN_A]
    repository.remove("user-a", TOKEN_A)  # bukan miliknya lagi → tidak terhapus
    repository.remove_tokens([TOKEN_B])
    token_session.commit()
    assert repository.tokens_for("user-a") == []
    assert repository.tokens_for("user-b") == [TOKEN_A]


@pytest.fixture
def device_client(token_session):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    uow = MagicMock(spec=UnitOfWork)
    uow.commit.side_effect = token_session.commit
    user = MagicMock()
    user.id = "user-a"
    app.dependency_overrides.update({
        get_current_user: lambda: user,
        get_uow: lambda: uow,
        get_device_token_repository: lambda: SqlAlchemyDeviceTokenRepository(token_session),
    })
    with TestClient(app) as client:
        yield client, app, SqlAlchemyDeviceTokenRepository(token_session)


def test_register_and_unregister_device_endpoints(device_client):
    client, _, repository = device_client
    response = client.put("/notifications/devices", json={"token": TOKEN_A, "platform": "ANDROID"})
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Perangkat terdaftar untuk notifikasi", "data": None}
    assert client.put("/notifications/devices", json={"token": TOKEN_A}).status_code == 200
    assert repository.tokens_for("user-a") == [TOKEN_A]
    response = client.request("DELETE", "/notifications/devices", json={"token": TOKEN_A})
    assert response.status_code == 200
    assert repository.tokens_for("user-a") == []


def test_unregister_accepts_same_body_as_register(device_client):
    """Aplikasi Android mengirim {"token", "platform"} saat logout; dulu ditolak 422 dan token tertinggal."""
    client, _, repository = device_client
    client.put("/notifications/devices", json={"token": TOKEN_A, "platform": "ANDROID"})
    response = client.request("DELETE", "/notifications/devices", json={"token": TOKEN_A, "platform": "ANDROID"})
    assert response.status_code == 200
    assert repository.tokens_for("user-a") == []


@pytest.mark.parametrize("body", [
    {}, {"token": "pendek"}, {"token": "ada spasi di tengah token ini"},
    {"token": TOKEN_A, "platform": "IOS"}, {"token": TOKEN_A, "user_id": "user-b"},
])
def test_register_device_validation(device_client, body):
    client, _, repository = device_client
    assert client.put("/notifications/devices", json=body).status_code == 422
    assert repository.tokens_for("user-a") == []


def test_device_endpoints_require_login(device_client):
    client, app, _ = device_client
    app.dependency_overrides.pop(get_current_user)
    assert client.put("/notifications/devices", json={"token": TOKEN_A}).status_code == 401
    assert client.request("DELETE", "/notifications/devices", json={"token": TOKEN_A}).status_code == 401
