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


@dataclass(frozen=True)
class AuthenticatedMatchingUser:
    user_id: str
    role: UserRole


def get_authenticated_matching_user(
    user: User = Depends(get_current_user),
) -> AuthenticatedMatchingUser:
    return AuthenticatedMatchingUser(user_id=user.id, role=user.role)


def get_matching_repository(
    db: Session = Depends(get_db),
) -> MatchingRepository:
    return SqlAlchemyMatchingRepository(
        session=db
    )


def get_recommend_freelancers_use_case(
    repository: MatchingRepository = Depends(
        get_matching_repository
    ),
) -> RecommendFreelancersForProject:
    return RecommendFreelancersForProject(
        repository=repository
    )


def get_recommend_projects_use_case(
    repository: MatchingRepository = Depends(
        get_matching_repository
    ),
) -> RecommendProjectsForFreelancer:
    return RecommendProjectsForFreelancer(
        repository=repository
    )
