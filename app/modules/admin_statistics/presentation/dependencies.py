
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.core.exceptions import (
    UnauthorizedError,
)

from app.modules.admin_statistics.domain.entities import (
    AdminActor,
)

from app.modules.admin_statistics.infrastructure.repositories import (
    SqlAlchemyAdminStatisticsRepository,
)


# ============================================================
# 1. ADMIN AUTHENTICATION
# ============================================================

def get_authenticated_admin_actor() -> AdminActor:
    """
    Mengambil identitas Admin dari JWT.

    Implementasi sementara: FAIL-CLOSED.

    Semua request nyata ditolak dengan 401
    sampai Auth Module terintegrasi.

    Jangan mengambil role/user_id dari:
    - Query parameter
    - Request body
    - Header bebas buatan client
    """

    raise UnauthorizedError(
        "Autentikasi Admin belum "
        "terintegrasi dengan JWT"
    )


# ============================================================
# 2. ADMIN REPOSITORY DEPENDENCY
# ============================================================

def get_admin_statistics_repository(
    session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> SqlAlchemyAdminStatisticsRepository:
    """
    Membuat Repository dengan SQLAlchemy Session.

    Repository ini hanya menjalankan
    operasi SELECT.

    Tidak memerlukan commit().
    """

    return SqlAlchemyAdminStatisticsRepository(
        session=session,
    )