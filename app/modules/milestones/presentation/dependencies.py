from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError

from app.modules.milestones.application.dto import (
    MilestoneActor,
)

from app.modules.milestones.infrastructure.repositories import (
    SqlAlchemyMilestoneRepository,
)


# ============================================================
# 1. AUTHENTICATED USER DEPENDENCY
# ============================================================

def get_authenticated_milestone_actor() -> MilestoneActor:
    """
    FAIL-CLOSED AUTHENTICATION.

    Belum terhubung ke JWT Zaid.

    Jangan mengambil user_id / role dari
    Header, Query, atau Body tanpa JWT valid.

    Dependency ini hanya boleh diganti
    dengan integrasi autentikasi resmi.
    """

    raise UnauthorizedError(
        "Autentikasi Milestones belum "
        "terintegrasi dengan JWT"
    )


# ============================================================
# 2. MILESTONE REPOSITORY DEPENDENCY
# ============================================================

def get_milestone_repository(
    session: Annotated[Session, Depends(get_db)],
) -> SqlAlchemyMilestoneRepository:
    """
    Membuat Repository menggunakan
    SQLAlchemy Session dari app/core/database.py.
    """

    return SqlAlchemyMilestoneRepository(
        session=session,
    )


# ============================================================
# 3. SERVER DATE DEPENDENCY
# ============================================================

def get_milestone_today() -> date:
    """
    Tanggal diambil dari server.

    UTC digunakan sebagai default sementara.

    Tidak menerima tanggal yang diklaim
    oleh client untuk perhitungan risk.
    """

    return datetime.now(
        timezone.utc
    ).date()
