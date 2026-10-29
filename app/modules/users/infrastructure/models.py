from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UpdatedAt, UuidPk


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UuidPk]
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    phone_number: Mapped[str | None] = mapped_column(String(20))
    profile_image_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
