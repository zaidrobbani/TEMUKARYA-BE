from datetime import datetime

from sqlalchemy import CHAR, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UuidPk


class RevokedTokenModel(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=3), index=True)
    created_at: Mapped[CreatedAt]


class AuthActionTokenModel(Base):
    __tablename__ = "auth_action_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_auth_action_tokens_token_hash"),
        Index("ix_auth_action_tokens_user_purpose_created", "user_id", "purpose", "created_at"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(30))
    token_hash: Mapped[str] = mapped_column(CHAR(64))
    expires_at: Mapped[datetime] = mapped_column(mysql.DATETIME(fsp=3))
    used_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=3))
    created_at: Mapped[CreatedAt]
