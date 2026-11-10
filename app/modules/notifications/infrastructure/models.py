from datetime import datetime

from sqlalchemy import CHAR, ForeignKey, Index, String, Text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UuidPk
from app.modules.users.infrastructure import models as _users_models  # noqa: F401


class NotificationModel(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created_at", "user_id", "created_at"),
        Index("ix_notifications_user_read_at", "user_id", "read_at"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.id", ondelete="CASCADE"))
    notification_type: Mapped[str] = mapped_column(String(45))
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text)
    reference_type: Mapped[str | None] = mapped_column(String(40))
    reference_id: Mapped[str | None] = mapped_column(CHAR(36))
    created_at: Mapped[CreatedAt]
    read_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=3))
