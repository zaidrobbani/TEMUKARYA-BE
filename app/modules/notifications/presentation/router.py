from fastapi import APIRouter, Depends, Query

from app.core.responses import ApiResponse, error_responses, success_response
from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.notifications.application.use_cases import (
    CountUnreadNotifications,
    ListNotifications,
    MarkAllNotificationsRead,
    MarkNotificationRead,
)
from app.modules.notifications.domain.entities import NotificationCategory
from app.modules.notifications.presentation.dependencies import (
    count_unread_use_case,
    list_notifications_use_case,
    mark_all_read_use_case,
    mark_read_use_case,
)
from app.modules.notifications.presentation.schemas import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.modules.users.domain.entities import User

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
):
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
):
    return success_response("Jumlah notifikasi belum dibaca", {"unread_count": use_case.execute(user.id)})


@router.patch("/read-all", response_model=ApiResponse[MarkAllReadResponse], responses=error_responses(401))
def mark_all_read(
    user: User = Depends(get_current_user),
    use_case: MarkAllNotificationsRead = Depends(mark_all_read_use_case),
):
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
):
    notification = use_case.execute(user.id, notification_id)
    return success_response("Notifikasi ditandai sudah dibaca", NotificationResponse.from_entity(notification))
