
from fastapi import APIRouter, Depends, Path, Query
from fastapi import status

from app.core.exceptions import ForbiddenError

from app.modules.users.domain.entities import UserRole

from app.modules.matching.application.dto import (
    RecommendFreelancersInput,
    RecommendProjectsInput,
)

from app.modules.matching.application.use_cases import (
    RecommendFreelancersForProject,
    RecommendProjectsForFreelancer,
)

from app.modules.matching.presentation.dependencies import (
    AuthenticatedMatchingUser,
    get_authenticated_matching_user,
    get_recommend_freelancers_use_case,
    get_recommend_projects_use_case,
)

from app.modules.matching.presentation.schemas import (
    FreelancerRecommendationsPageResponse,
    ProjectRecommendationsPageResponse,
)


# ============================================================
# MATCHING ROUTER
# ============================================================

router = APIRouter(
    tags=["matching"],
)


# ============================================================
# 1. RECOMMEND FREELANCERS FOR UMKM
# ============================================================

@router.get(
    "/projects/{project_id}/recommendations/freelancers",
    response_model=FreelancerRecommendationsPageResponse,
    status_code=status.HTTP_200_OK,
    summary="Recommend Freelancers for Project",
    description=(
        "Mengembalikan rekomendasi Freelancer "
        "berdasarkan kecocokan skill dengan project "
        "milik UMKM. Minimum matching score 60%."
    ),
)
def recommend_freelancers_for_project(
    project_id: str = Path(
        min_length=1,
        max_length=36,
        description="UUID project milik UMKM",
    ),

    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),

    offset: int = Query(
        default=0,
        ge=0,
        le=10000,
    ),

    current_user: AuthenticatedMatchingUser = Depends(
        get_authenticated_matching_user
    ),

    use_case: RecommendFreelancersForProject = Depends(
        get_recommend_freelancers_use_case
    ),
) -> FreelancerRecommendationsPageResponse:

    # ========================================================
    # 1. ROLE AUTHORIZATION
    # ========================================================

    if current_user.role != UserRole.UMKM:
        raise ForbiddenError(
            "Hanya UMKM yang dapat meminta "
            "rekomendasi Freelancer"
        )

    # ========================================================
    # 2. BUILD APPLICATION INPUT
    # ========================================================

    # umkm_id WAJIB berasal dari authenticated user,
    # bukan dari input query parameter.

    data = RecommendFreelancersInput(
        project_id=project_id,
        umkm_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )

    # ========================================================
    # 3. EXECUTE USE CASE
    # ========================================================

    result = use_case.execute(data)

    # ========================================================
    # 4. RETURN VALIDATED JSON RESPONSE
    # ========================================================

    return (
        FreelancerRecommendationsPageResponse
        .model_validate(result)
    )


# ============================================================
# 2. RECOMMEND PROJECTS FOR FREELANCER
# ============================================================

@router.get(
    "/freelancers/me/recommendations/projects",
    response_model=ProjectRecommendationsPageResponse,
    status_code=status.HTTP_200_OK,
    summary="Recommend Projects for Freelancer",
    description=(
        "Mengembalikan rekomendasi project TERBUKA "
        "yang sudah dipublikasikan, berdasarkan "
        "kecocokan dengan skill Freelancer. "
        "Minimum matching score 60%."
    ),
)
def recommend_projects_for_freelancer(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),

    offset: int = Query(
        default=0,
        ge=0,
        le=10000,
    ),

    current_user: AuthenticatedMatchingUser = Depends(
        get_authenticated_matching_user
    ),

    use_case: RecommendProjectsForFreelancer = Depends(
        get_recommend_projects_use_case
    ),
) -> ProjectRecommendationsPageResponse:

    # ========================================================
    # 1. ROLE AUTHORIZATION
    # ========================================================

    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError(
            "Hanya Freelancer yang dapat meminta "
            "rekomendasi Project"
        )

    # ========================================================
    # 2. BUILD APPLICATION INPUT
    # ========================================================

    # freelancer_id berasal dari JWT user,
    # bukan berasal dari request client.

    data = RecommendProjectsInput(
        freelancer_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )

    # ========================================================
    # 3. EXECUTE USE CASE
    # ========================================================

    result = use_case.execute(data)

    # ========================================================
    # 4. RETURN VALIDATED JSON RESPONSE
    # ========================================================

    return (
        ProjectRecommendationsPageResponse
        .model_validate(result)
    )