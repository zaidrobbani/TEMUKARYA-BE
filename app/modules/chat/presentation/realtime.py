import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

import anyio
from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.dependencies import get_token_service
from app.core.json_types import JsonObject
from app.modules.auth.application.use_cases import AuthenticateToken
from app.modules.auth.infrastructure.repositories import SqlAlchemyRevokedTokenRepository
from app.modules.chat.domain.entities import ChatActor
from app.modules.chat.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.modules.chat.presentation.dependencies import ChatDatabaseContext
from app.modules.users.infrastructure.repositories import SqlAlchemyUserRepository

logger = logging.getLogger(__name__)

CLOSE_UNAUTHORIZED = 4401
CLOSE_NOT_FOUND = 4404


class ChatHub:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def join(self, conversation_id: str, socket: WebSocket) -> None:
        async with self._lock:
            self._rooms[conversation_id].add(socket)

    async def leave(self, conversation_id: str, socket: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(conversation_id)
            if room is not None:
                room.discard(socket)
                if not room:
                    self._rooms.pop(conversation_id, None)

    def connection_count(self, conversation_id: str) -> int:
        return len(self._rooms.get(conversation_id, ()))

    async def broadcast(self, conversation_id: str, payload: JsonObject) -> None:
        async with self._lock:
            targets = list(self._rooms.get(conversation_id, ()))
        for socket in targets:
            try:
                await socket.send_json(payload)
            except Exception:
                await self.leave(conversation_id, socket)

    def broadcast_from_thread(self, conversation_id: str, payload: JsonObject) -> None:
        try:
            anyio.from_thread.run(self.broadcast, conversation_id, payload)
        except Exception:
            logger.exception("Broadcast chat gagal untuk percakapan %s", conversation_id)


chat_hub = ChatHub()


def get_chat_hub() -> ChatHub:
    return chat_hub


ChatContextFactory = Callable[[], AbstractContextManager[ChatDatabaseContext]]


@contextmanager
def _open_chat_context() -> Iterator[ChatDatabaseContext]:
    session = SessionLocal()
    try:
        yield ChatDatabaseContext(
            session=session,
            conversations=SqlAlchemyConversationRepository(session),
            messages=SqlAlchemyMessageRepository(session),
        )
    finally:
        session.close()


def get_chat_context_factory() -> ChatContextFactory:
    return _open_chat_context


SocketAuthenticator = Callable[[str], ChatActor]


def _authenticate(token: str) -> ChatActor:
    session = SessionLocal()
    try:
        use_case = AuthenticateToken(
            SqlAlchemyUserRepository(session),
            SqlAlchemyRevokedTokenRepository(session),
            get_token_service(),
        )
        user = use_case.execute(token).user
        return ChatActor(user_id=user.id, role=user.role)
    finally:
        session.close()


def get_socket_authenticator() -> SocketAuthenticator:
    return _authenticate


MessageNotifier = Callable[[Session, str, str, str], None]


def get_socket_message_notifier() -> MessageNotifier:
    from app.modules.notifications.infrastructure.hooks import notify_new_message

    return notify_new_message


def token_from(socket: WebSocket) -> str | None:
    header = socket.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return socket.query_params.get("token") or None
