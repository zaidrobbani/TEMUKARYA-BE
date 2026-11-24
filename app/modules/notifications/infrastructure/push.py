"""
Push notifikasi ke HP lewat Firebase Cloud Messaging (HTTP v1 API).

Alur: notifikasi baru di-COMMIT → `after_commit` (lihat realtime.py) memanggil `push_dispatcher().dispatch(...)`
→ dikirim di thread latar (request tidak menunggu Google) ke semua token perangkat milik user penerima.
Token yang ditolak FCM (aplikasi di-uninstall, token kedaluwarsa) langsung dihapus.

Kredensial: file JSON service account Firebase, path-nya di env `FIREBASE_CREDENTIALS_FILE`.
Bila kosong atau file tidak ada, push nonaktif (no-op) dan fitur lain tetap berjalan.
Pesan dikirim sebagai *data message* prioritas tinggi supaya aplikasi Android sendiri yang menampilkan
notifikasi (channel, ikon, dan tujuan saat diketuk diatur di aplikasi), baik saat aplikasi dibuka maupun ditutup.
"""

import json
import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import httpx
import jwt
from sqlalchemy.orm import Session

from app.modules.notifications.domain.entities import Notification
from app.modules.notifications.domain.repositories import DeviceTokenRepository

logger = logging.getLogger(__name__)

_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
_TOKEN_TTL_SECONDS = 3600
_REFRESH_MARGIN_SECONDS = 300


class SendResult(Enum):
    SENT = "SENT"
    INVALID_TOKEN = "INVALID_TOKEN"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ServiceAccount:
    project_id: str
    client_email: str
    private_key: str
    private_key_id: str
    token_uri: str

    @classmethod
    def from_file(cls, path: str) -> "ServiceAccount":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("type") != "service_account":
            raise ValueError("Bukan file service account (field type harus 'service_account')")
        return cls(
            project_id=data["project_id"],
            client_email=data["client_email"],
            private_key=data["private_key"],
            private_key_id=data.get("private_key_id", ""),
            token_uri=data.get("token_uri") or "https://oauth2.googleapis.com/token",
        )


class FcmClient:
    def __init__(self, account: ServiceAccount, http: httpx.Client | None = None, clock: Callable[[], float] = time.time):
        self._account = account
        self._http = http or httpx.Client(timeout=10)
        self._clock = clock
        self._lock = threading.Lock()
        self._access_token: str | None = None
        self._expires_at = 0.0

    def _token(self) -> str:
        with self._lock:
            now = self._clock()
            if self._access_token and now < self._expires_at - _REFRESH_MARGIN_SECONDS:
                return self._access_token
            assertion = jwt.encode(
                {
                    "iss": self._account.client_email,
                    "scope": _SCOPE,
                    "aud": self._account.token_uri,
                    "iat": int(now),
                    "exp": int(now) + _TOKEN_TTL_SECONDS,
                },
                self._account.private_key,
                algorithm="RS256",
                headers={"kid": self._account.private_key_id} if self._account.private_key_id else None,
            )
            response = self._http.post(
                self._account.token_uri,
                data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
            )
            response.raise_for_status()
            body = response.json()
            self._access_token = body["access_token"]
            self._expires_at = now + int(body.get("expires_in", _TOKEN_TTL_SECONDS))
            return self._access_token

    def send(self, token: str, data: dict[str, str]) -> SendResult:
        try:
            access_token = self._token()
        except Exception:
            logger.exception("Gagal mengambil access token Firebase; cek FIREBASE_CREDENTIALS_FILE")
            return SendResult.FAILED
        message = {
            "message": {
                "token": token,
                "data": data,
                "android": {"priority": "HIGH", "ttl": "86400s"},
            }
        }
        try:
            response = self._http.post(
                _SEND_URL.format(project_id=self._account.project_id),
                json=message,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError:
            logger.warning("FCM tidak dapat dihubungi", exc_info=True)
            return SendResult.FAILED
        if response.status_code == 200:
            return SendResult.SENT
        if _is_invalid_token(response):
            return SendResult.INVALID_TOKEN
        if response.status_code in (401, 403):
            with self._lock:
                self._access_token = None  # paksa ambil ulang di kiriman berikutnya
        logger.warning("FCM menolak pesan (%s): %s", response.status_code, response.text[:300])
        return SendResult.FAILED


def _is_invalid_token(response: httpx.Response) -> bool:
    if response.status_code not in (400, 404):
        return False
    try:
        error = response.json().get("error", {})
    except ValueError:
        return False
    codes = {detail.get("errorCode") for detail in error.get("details", []) if isinstance(detail, dict)}
    if "UNREGISTERED" in codes or error.get("status") == "NOT_FOUND":
        return True
    # INVALID_ARGUMENT untuk token rusak; payload kita selalu valid sehingga ini berarti tokennya.
    return response.status_code == 400 and ("INVALID_ARGUMENT" in codes or error.get("status") == "INVALID_ARGUMENT")


def notification_data(notification: Notification) -> dict[str, str]:
    """FCM data message hanya menerima string."""
    return {
        "notification_id": notification.id,
        "type": notification.notification_type,
        "category": notification.category.value,
        "title": notification.title,
        "body": notification.body,
        "reference_type": notification.reference_type or "",
        "reference_id": notification.reference_id or "",
    }


class PushDispatcher:
    def __init__(
        self,
        client: FcmClient | None,
        session_factory: Callable[[], Session],
        executor: ThreadPoolExecutor | None = None,
        repository_factory: Callable[[Session], DeviceTokenRepository] | None = None,
    ):
        self._client = client
        self._session_factory = session_factory
        self._repository_factory = repository_factory
        self._executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="fcm-push")

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def dispatch(self, notification: Notification) -> None:
        if self._client is None:
            return
        try:
            self._executor.submit(self.deliver, notification)
        except RuntimeError:
            logger.warning("Executor push sudah berhenti; notifikasi %s tidak dikirim", notification.id)

    def deliver(self, notification: Notification) -> None:
        if self._client is None:
            return
        session = self._session_factory()
        try:
            if self._repository_factory is None:
                from app.modules.notifications.infrastructure.device_tokens import SqlAlchemyDeviceTokenRepository

                repository: DeviceTokenRepository = SqlAlchemyDeviceTokenRepository(session)
            else:
                repository = self._repository_factory(session)
            data = notification_data(notification)
            invalid = [
                token for token in repository.tokens_for(notification.user_id)
                if self._client.send(token, data) is SendResult.INVALID_TOKEN
            ]
            if invalid:
                repository.remove_tokens(invalid)
                session.commit()
        except Exception:
            session.rollback()
            logger.exception("Push FCM gagal untuk notifikasi %s", notification.id)
        finally:
            session.close()


_dispatcher: PushDispatcher | None = None
_dispatcher_lock = threading.Lock()


def build_dispatcher(credentials_file: str, session_factory: Callable[[], Session]) -> PushDispatcher:
    path = credentials_file.strip()
    if not path:
        logger.info("FIREBASE_CREDENTIALS_FILE kosong: push notifikasi FCM nonaktif")
        return PushDispatcher(None, session_factory)
    try:
        account = ServiceAccount.from_file(path)
    except (OSError, ValueError, KeyError) as exc:
        logger.warning("Push FCM nonaktif, kredensial %s tidak bisa dibaca: %s", path, exc)
        return PushDispatcher(None, session_factory)
    logger.info("Push FCM aktif untuk project Firebase %s", account.project_id)
    return PushDispatcher(FcmClient(account), session_factory)


def push_dispatcher() -> PushDispatcher:
    global _dispatcher
    if _dispatcher is None:
        with _dispatcher_lock:
            if _dispatcher is None:
                from app.core.config import settings
                from app.core.database import SessionLocal

                _dispatcher = build_dispatcher(settings.FIREBASE_CREDENTIALS_FILE, SessionLocal)
    return _dispatcher
