from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.users.domain.entities import User, UserRole

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
    user: User = Depends(get_current_user),
) -> AuthenticatedDiscoveryUser:
    return AuthenticatedDiscoveryUser(user_id=user.id, role=user.role)


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