from datetime import date, datetime

from sqlalchemy import CHAR, CheckConstraint, Date, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UpdatedAt, UuidPk
from app.modules.applications.infrastructure import models as _applications_models  # noqa: F401
from app.modules.projects.infrastructure import models as _projects_models  # noqa: F401


class ProjectAgreementModel(Base):
    __tablename__ = "project_agreements"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_agreements_project"),
        CheckConstraint("agreed_price > 0", name="ck_project_agreements_price_positive"),
        CheckConstraint(
            "(selection_source = 'APPLICATION') = (application_id IS NOT NULL)",
            name="ck_project_agreements_application_source",
        ),
    )

    id: Mapped[UuidPk]
    project_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("projects.id", ondelete="RESTRICT"))
    freelancer_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("freelancer_profiles.user_id", ondelete="RESTRICT")
    )
    application_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("project_applications.id", ondelete="RESTRICT")
    )
    selection_source: Mapped[str] = mapped_column(String(30))
    scope_of_work: Mapped[str] = mapped_column(Text)
    agreed_price: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True))
    agreed_deadline: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(35), server_default=text("'PENDING_APPROVAL'"))
    agreement_version: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), server_default=text("'1'"))
    umkm_approved_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=3))
    freelancer_approved_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=3))
    change_request_note: Mapped[str | None] = mapped_column(Text)
    change_requested_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=3))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class ProjectStatusHistoryModel(Base):
    __tablename__ = "project_status_history"
    __table_args__ = (Index("ix_project_status_history_project_changed_at", "project_id", "changed_at"),)

    id: Mapped[UuidPk]
    project_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("projects.id", ondelete="RESTRICT"))
    previous_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(50))
    change_reason: Mapped[str | None] = mapped_column(Text)
    change_source: Mapped[str] = mapped_column(String(15), server_default=text("'USER'"))
    changed_by_user_id: Mapped[str | None] = mapped_column(CHAR(36), ForeignKey("users.id", ondelete="RESTRICT"))
    changed_at: Mapped[CreatedAt]
    reason_code: Mapped[str | None] = mapped_column(String(40))
