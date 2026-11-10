from datetime import datetime

from sqlalchemy import CHAR, JSON, CheckConstraint, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UuidPk
from app.modules.projects.infrastructure import models as _projects_models  # noqa: F401
from app.modules.users.infrastructure import models as _users_models  # noqa: F401


def _now_column() -> Mapped[datetime]:
    return mapped_column(mysql.DATETIME(fsp=3), server_default=text("CURRENT_TIMESTAMP(3)"))


class ProjectSubmissionModel(Base):
    __tablename__ = "project_submissions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_project_submissions_project_version"),
    )

    id: Mapped[UuidPk]
    project_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("projects.id", ondelete="RESTRICT"))
    version_number: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True))
    submission_note: Mapped[str | None] = mapped_column(Text)
    result_url: Mapped[str | None] = mapped_column(String(1000))
    submitted_at: Mapped[datetime] = _now_column()


class SubmissionFileModel(Base):
    __tablename__ = "submission_files"

    id: Mapped[UuidPk]
    submission_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("project_submissions.id", ondelete="CASCADE")
    )
    original_file_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True))
    uploaded_at: Mapped[datetime] = _now_column()


class SubmissionReviewModel(Base):
    __tablename__ = "submission_reviews"
    __table_args__ = (
        UniqueConstraint("submission_id", name="uq_submission_reviews_submission"),
        CheckConstraint(
            "decision <> 'REVISION_REQUESTED' OR (review_note IS NOT NULL AND review_note <> '')",
            name="ck_submission_reviews_revision_note",
        ),
    )

    id: Mapped[UuidPk]
    submission_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("project_submissions.id", ondelete="RESTRICT")
    )
    reviewer_user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.id", ondelete="RESTRICT"))
    decision: Mapped[str] = mapped_column(String(25))
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = _now_column()
    focus_areas: Mapped[list | None] = mapped_column(JSON)
    revision_items: Mapped[list | None] = mapped_column(JSON)
