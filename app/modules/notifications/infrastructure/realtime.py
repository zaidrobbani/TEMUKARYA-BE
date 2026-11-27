import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable

from fastapi import WebSocket
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.json_types import JsonObject
from app.modules.notifications.domain.entities import Notification

logger = logging.getLogger(__name__)
_PENDING_KEY = "temukarya_pending_notifications"


class NotificationHub:
    def __init__(self) -> None:
        self._sockets: dict[str, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None
        self.serialize: Callable[[Notification], JsonObject] = lambda n: {"id": n.id}

    async def join(self, user_id: str, socket: WebSocket) -> None:
        self._loop = asyncio.get_running_loop()
        self._sockets[user_id].add(socket)

    async def leave(self, user_id: str, socket: WebSocket) -> None:
        sockets = self._sockets.get(user_id)
        if sockets is not None:
            sockets.discard(socket)
            if not sockets:
                self._sockets.pop(user_id, None)

    def connection_count(self, user_id: str) -> int:
        return len(self._sockets.get(user_id, ()))

    async def send(self, user_id: str, notification: Notification) -> None:
        payload = {"type": "notification", "notification": self.serialize(notification)}
        for socket in list(self._sockets.get(user_id, ())):
            try:
                await socket.send_json(payload)
            except Exception:
                await self.leave(user_id, socket)

    def publish(self, notification: Notification) -> None:
        loop = self._loop
        if loop is None or loop.is_closed() or not self._sockets.get(notification.user_id):
            return
        coroutine = self.send(notification.user_id, notification)
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        try:
            if running is loop:
                loop.create_task(coroutine)
            else:
                asyncio.run_coroutine_threadsafe(coroutine, loop)
        except Exception:
            coroutine.close()
            logger.exception("Push notifikasi gagal untuk user %s", notification.user_id)


notification_hub = NotificationHub()


def queue_after_commit(session: Session, notification: Notification) -> None:
    session.info.setdefault(_PENDING_KEY, []).append(notification)


@event.listens_for(Session, "after_commit")
def _publish_committed(session: Session) -> None:
    pending = session.info.pop(_PENDING_KEY, None) or ()
    if not pending:
        return
    from app.modules.notifications.infrastructure.push import push_dispatcher

    dispatcher = push_dispatcher()
    for notification in pending:
        notification_hub.publish(notification)
        dispatcher.dispatch(notification)


@event.listens_for(Session, "after_rollback")
def _drop_rolled_back(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)
