
from datetime import datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProjectApplicationModel(Base):
    """
    ORM untuk tabel project_applications.

    Relasi FK ke projects dan freelancer_profiles
    sudah ditegakkan oleh schema MySQL.

    Referensi ForeignKey ORM belum dideklarasikan
    karena model parent berada pada PR lain
    yang belum terintegrasi ke branch dev.
    """

    __tablename__ = "project_applications"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "freelancer_id",
            name="uq_project_applications_project_freelancer",
        ),
        CheckConstraint(
            "proposed_price > 0",
            name="ck_project_applications_price_positive",
        ),
        CheckConstraint(
            "estimated_duration_days > 0",
            name="ck_project_applications_duration_positive",
        ),
    )

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        server_default=text("(UUID())"),
    )

    project_id: Mapped[str] = mapped_column(
        CHAR(36),
        nullable=False,
    )

    freelancer_id: Mapped[str] = mapped_column(
        CHAR(36),
        nullable=False,
    )

    proposed_price: Mapped[int] = mapped_column(
        mysql.BIGINT(unsigned=True),
        nullable=False,
    )

    estimated_duration_days: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        nullable=False,
    )

    proposal_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'SUBMITTED'"),
    )

    submitted_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
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