from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app.core.responses import ApiResponse, SuccessBody, error_responses, success_response
from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.notifications.application.use_cases import (
    CountUnreadNotifications,
    ListNotifications,
    MarkAllNotificationsRead,
    MarkNotificationRead,
    RegisterDeviceToken,
    UnregisterDeviceToken,
)
from app.modules.notifications.domain.entities import NotificationCategory
from app.modules.notifications.infrastructure.realtime import NotificationHub
from app.modules.notifications.presentation.dependencies import (
    count_unread_use_case,
    get_notification_hub,
    get_notification_socket_authenticator,
    get_unread_counter,
    list_notifications_use_case,
    mark_all_read_use_case,
    mark_read_use_case,
    register_device_use_case,
    unregister_device_use_case,
)
from app.modules.notifications.presentation.schemas import (
    DeviceTokenDeleteRequest,
    DeviceTokenRequest,
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.modules.users.domain.entities import User
from app.core.json_types import JsonObject
from app.modules.notifications.domain.entities import Notification
from app.modules.notifications.presentation.dependencies import SocketAuthenticator, UnreadCounter

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "",
    response_model=ApiResponse[NotificationListResponse],
    responses=error_responses(400, 401, 422),
)
def list_notifications(
    category: NotificationCategory | None = Query(None, description="PROJECT, PAYMENT, atau MESSAGE"),
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    use_case: ListNotifications = Depends(list_notifications_use_case),
) -> SuccessBody[NotificationListResponse]:
    page = use_case.execute(user.id, category, unread_only, limit, offset)
    return success_response(
        "Daftar notifikasi",
        NotificationListResponse(
            items=[NotificationResponse.from_entity(n) for n in page.items],
            limit=limit,
            offset=offset,
            has_more=page.has_more,
            unread_count=page.unread_count,
            counts=page.category_counts,
        ),
    )


@router.get("/unread-count", response_model=ApiResponse[UnreadCountResponse], responses=error_responses(401))
def unread_count(
    user: User = Depends(get_current_user),
    use_case: CountUnreadNotifications = Depends(count_unread_use_case),
) -> SuccessBody[UnreadCountResponse]:
    return success_response("Jumlah notifikasi belum dibaca", {"unread_count": use_case.execute(user.id)})


@router.patch("/read-all", response_model=ApiResponse[MarkAllReadResponse], responses=error_responses(401))
def mark_all_read(
    user: User = Depends(get_current_user),
    use_case: MarkAllNotificationsRead = Depends(mark_all_read_use_case),
) -> SuccessBody[MarkAllReadResponse]:
    return success_response("Semua notifikasi ditandai sudah dibaca", {"updated": use_case.execute(user.id)})


@router.patch(
    "/{notification_id}/read",
    response_model=ApiResponse[NotificationResponse],
    responses=error_responses(401, 404),
)
def mark_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    use_case: MarkNotificationRead = Depends(mark_read_use_case),
) -> SuccessBody[NotificationResponse]:
    notification = use_case.execute(user.id, notification_id)
    return success_response("Notifikasi ditandai sudah dibaca", NotificationResponse.from_entity(notification))


@router.put(
    "/devices",
    response_model=ApiResponse[None],
    responses=error_responses(401, 422),
    summary="Daftarkan token FCM perangkat ini",
    description=(
        "Dipanggil aplikasi setelah login dan setiap token FCM berganti. Idempoten; token yang sebelumnya "
        "terdaftar ke akun lain dipindahkan ke akun ini."
    ),
)
def register_device(
    body: DeviceTokenRequest,
    user: User = Depends(get_current_user),
    use_case: RegisterDeviceToken = Depends(register_device_use_case),
) -> SuccessBody[None]:
    use_case.execute(user.id, body.token, body.platform)
    return success_response("Perangkat terdaftar untuk notifikasi")


@router.delete(
    "/devices",
    response_model=ApiResponse[None],
    responses=error_responses(401, 422),
    summary="Hapus token FCM perangkat ini (saat logout)",
)
def unregister_device(
    body: DeviceTokenDeleteRequest,
    user: User = Depends(get_current_user),
    use_case: UnregisterDeviceToken = Depends(unregister_device_use_case),
) -> SuccessBody[None]:
    use_case.execute(user.id, body.token)
    return success_response("Perangkat dihapus dari notifikasi")


CLOSE_UNAUTHORIZED = 4401


def _serialize(notification: Notification) -> JsonObject:
    return NotificationResponse.from_entity(notification).model_dump(mode="json")


def _token_from(socket: WebSocket) -> str | None:
    header = socket.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return socket.query_params.get("token") or None


@router.websocket("/ws")
async def notification_socket(
    socket: WebSocket,
    authenticate: SocketAuthenticator = Depends(get_notification_socket_authenticator),
    count_unread: UnreadCounter = Depends(get_unread_counter),
    hub: NotificationHub = Depends(get_notification_hub),
) -> None:
    await socket.accept()
    token = _token_from(socket)
    try:
        user_id = await run_in_threadpool(authenticate, token) if token else None
    except Exception:
        user_id = None
    if user_id is None:
        await socket.close(code=CLOSE_UNAUTHORIZED, reason="Sesi tidak valid")
        return

    hub.serialize = _serialize
    await hub.join(user_id, socket)
    try:
        unread = await run_in_threadpool(count_unread, user_id)
        await socket.send_json({"type": "ready", "unread_count": unread})
        while True:
            data = await socket.receive_json()
            if isinstance(data, dict) and data.get("type") == "ping":
                await socket.send_json({"type": "pong"})
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        await hub.leave(user_id, socket)
