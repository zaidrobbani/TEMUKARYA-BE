from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError

from app.modules.users.domain.entities import UserRole

from app.modules.discovery.application.use_cases import (
    GetFreelancerDetail,
    SearchFreelancers,
)

from app.modules.discovery.domain.repositories import (
    DiscoveryRepository,
)

from app.modules.discovery.infrastructure.repositories import (
    SqlAlchemyDiscoveryRepository,
)


# ============================================================
# AUTHENTICATED DISCOVERY USER
# ============================================================

@dataclass(frozen=True)
class AuthenticatedDiscoveryUser:
    user_id: str
    role: UserRole


def get_authenticated_discovery_user(
) -> AuthenticatedDiscoveryUser:
    """
    Fail-closed authentication.

    Sampai JWT Zaid terintegrasi,
    seluruh request tanpa dependency override
    harus menghasilkan 401 Unauthorized.

    Tidak menggunakan hardcoded user_id.
    Tidak mempercayai role dari query parameter.
    """
    raise UnauthorizedError(
        "Authentication belum terintegrasi"
    )


# ============================================================
# DISCOVERY REPOSITORY DEPENDENCY
# ============================================================

def get_discovery_repository(
    db: Session = Depends(get_db),
) -> DiscoveryRepository:

    return SqlAlchemyDiscoveryRepository(
        session=db
    )


# ============================================================
# SEARCH FREELANCERS USE CASE
# ============================================================

def get_search_freelancers_use_case(
    repository: DiscoveryRepository = Depends(
        get_discovery_repository
    ),
) -> SearchFreelancers:

    return SearchFreelancers(
        repository=repository
    )


# ============================================================
# GET FREELANCER DETAIL USE CASE
# ============================================================

def get_freelancer_detail_use_case(
    repository: DiscoveryRepository = Depends(
        get_discovery_repository
    ),
) -> GetFreelancerDetail:

    return GetFreelancerDetail(
        repository=repository
    )