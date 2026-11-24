from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# ============================================================
# PROJECT MILESTONE MODEL
# ============================================================

class ProjectMilestoneModel(Base):
    """
    Representasi tabel project_milestones
    menggunakan SQLAlchemy ORM.
    """

    __tablename__ = "project_milestones"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "sort_order",
            name="uq_project_milestones_project_order",
        ),
        CheckConstraint(
            "weight_percent > 0 AND weight_percent <= 100",
            name="ck_project_milestones_weight_range",
        ),
    )

    # ========================================================
    # 1. PRIMARY KEY
    # ========================================================

    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        server_default=text("(UUID())"),
    )

    # ========================================================
    # 2. PROJECT RELATION
    # ========================================================

    project_id: Mapped[str] = mapped_column(
        CHAR(36),
        ForeignKey(
            "projects.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    # ========================================================
    # 3. MILESTONE INFORMATION
    # ========================================================

    name: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # ========================================================
    # 4. WEIGHT
    # ========================================================

    weight_percent: Mapped[Decimal] = mapped_column(
        Numeric(
            5,
            2,
            asdecimal=True,
        ),
        nullable=False,
    )

    # ========================================================
    # 5. STATUS AND SORTING
    # ========================================================

    status: Mapped[str] = mapped_column(
        String(25),
        nullable=False,
        server_default=text("'BELUM_SELESAI'"),
    )

    sort_order: Mapped[int] = mapped_column(
        mysql.INTEGER(unsigned=True),
        nullable=False,
    )

    # ========================================================
    # 6. COMPLETION TRACKING
    # ========================================================

    completed_at: Mapped[
        datetime | None
    ] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=True,
    )

    updated_by_user_id: Mapped[
        str | None
    ] = mapped_column(
        CHAR(36),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    # ========================================================
    # 7. TIMESTAMPS
    # ========================================================

    created_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=False,
        server_default=text(
            "CURRENT_TIMESTAMP(3)"
        ),
    )

    updated_at: Mapped[datetime] = mapped_column(
        mysql.DATETIME(fsp=3),
        nullable=False,
        server_default=text(
            "CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"
        ),
    )