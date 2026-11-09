from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# 1. PROJECT MODEL

class ProjectModel(Base):
    __tablename__ = "projects"

    __table_args__ = (
        CheckConstraint(
            "budget > 0",
            name="ck_projects_budget_positive",
        ),
        Index(
            "ix_projects_status_published_at",
            "status",
            "published_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        server_default=text("(UUID())"),
    )

    umkm_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey(
            "umkm_profiles.user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    category_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey(
            "project_categories.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    budget: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        nullable=False,
    )

    deadline: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        server_default=text("'TERBUKA'"),
    )

    published_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=False,
        server_default=text(
            "CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"
        ),
    )


# 2. PROJECT SKILL MODEL

class ProjectSkillModel(Base):
    __tablename__ = "project_skills"

    project_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    skill_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey(
            "skills.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )


# 3. PROJECT ATTACHMENT MODEL

class ProjectAttachmentModel(Base):
    __tablename__ = "project_attachments"

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        server_default=text("(UUID())"),
    )

    project_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    original_file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        nullable=False,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )