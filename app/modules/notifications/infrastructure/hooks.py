"""Notifikasi untuk kejadian di modul lain (lamaran, chat). Ikut transaksi pemanggil, tidak commit."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.notifications.application.use_cases import Notifier
from app.modules.notifications.domain.entities import NotificationType, ReferenceType
from app.modules.notifications.infrastructure.repositories import SqlAlchemyNotificationRepository

_PREVIEW_LENGTH = 120


def notify_application_received(session: Session, project_id: str, freelancer_id: str) -> None:
    row = session.execute(
        text(
            "SELECT p.umkm_id, p.title, u.name FROM projects p JOIN users u ON u.id = :fid WHERE p.id = :pid"
        ),
        {"pid": project_id, "fid": freelancer_id},
    ).mappings().first()
    if row is None:
        return
    Notifier(SqlAlchemyNotificationRepository(session)).notify(
        row["umkm_id"],
        NotificationType.APPLICATION_RECEIVED,
        f"{row['name']} mengajukan diri",
        f"{row['title']} menunggu keputusanmu",
        ReferenceType.PROJECT,
        project_id,
    )


def notify_new_message(session: Session, conversation_id: str, sender_id: str, message_text: str) -> None:
    row = session.execute(
        text(
            "SELECT c.umkm_id, c.freelancer_id, u.name FROM conversations c "
            "JOIN users u ON u.id = :sid WHERE c.id = :cid"
        ),
        {"cid": conversation_id, "sid": sender_id},
    ).mappings().first()
    if row is None:
        return
    recipient = row["freelancer_id"] if sender_id == row["umkm_id"] else row["umkm_id"]
    preview = " ".join(message_text.split())
    if len(preview) > _PREVIEW_LENGTH:
        preview = preview[: _PREVIEW_LENGTH - 1] + "…"
    Notifier(SqlAlchemyNotificationRepository(session)).notify(
        recipient,
        NotificationType.NEW_MESSAGE,
        f"Pesan baru dari {row['name']}",
        f"“{preview}”",
        ReferenceType.CONVERSATION,
        conversation_id,
    )
