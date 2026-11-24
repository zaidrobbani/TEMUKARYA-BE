
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.users.domain.entities import User, UserRole

from app.modules.matching.application.use_cases import (
    RecommendFreelancersForProject,
    RecommendProjectsForFreelancer,
)

from app.modules.matching.domain.repositories import (
    MatchingRepository,
)

from app.modules.matching.infrastructure.repositories import (
    SqlAlchemyMatchingRepository,
)


# ============================================================
# 1. AUTHENTICATED MATCHING USER
# ============================================================

@dataclass(frozen=True)
class AuthenticatedMatchingUser:
    """Identitas user yang telah login (dari JWT)."""

    user_id: str
    role: UserRole


# ============================================================
# 2. AUTHENTICATION - FAIL CLOSED
# ============================================================

def get_authenticated_matching_user(
    user: User = Depends(get_current_user),
) -> AuthenticatedMatchingUser:
    return AuthenticatedMatchingUser(user_id=user.id, role=user.role)


# ============================================================
# 3. MATCHING REPOSITORY
# ============================================================

def get_matching_repository(
    db: Session = Depends(get_db),
) -> MatchingRepository:
    """
    Dependency injection untuk Repository.

    FastAPI menyediakan database Session,
    lalu Repository menggunakannya untuk
    membaca data Matching.
    """

    return SqlAlchemyMatchingRepository(
        session=db
    )


# ============================================================
# 4. RECOMMEND FREELANCERS USE CASE
# ============================================================

def get_recommend_freelancers_use_case(
    repository: MatchingRepository = Depends(
        get_matching_repository
    ),
) -> RecommendFreelancersForProject:

    return RecommendFreelancersForProject(
        repository=repository
    )


# ============================================================
# 5. RECOMMEND PROJECTS USE CASE
# ============================================================

def get_recommend_projects_use_case(
    repository: MatchingRepository = Depends(
        get_matching_repository
    ),
) -> RecommendProjectsForFreelancer:

    return RecommendProjectsForFreelancer(
        repository=repository
    )