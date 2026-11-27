from fastapi import APIRouter, Depends, Path, Query

from app.core.exceptions import ForbiddenError
from app.core.responses import ApiResponse, SuccessBody, error_responses, success_response

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


router = APIRouter(
    tags=["matching"],
)


@router.get(
    "/projects/{project_id}/recommendations/freelancers",
    response_model=ApiResponse[FreelancerRecommendationsPageResponse],
    responses=error_responses(400, 401, 403, 404, 409, 422),
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
) -> SuccessBody[FreelancerRecommendationsPageResponse]:
    if current_user.role != UserRole.UMKM:
        raise ForbiddenError(
            "Hanya UMKM yang dapat meminta "
            "rekomendasi Freelancer"
        )

    data = RecommendFreelancersInput(
        project_id=project_id,
        umkm_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )

    result = use_case.execute(data)

    return success_response(
        "Rekomendasi Freelancer berhasil diambil",
        FreelancerRecommendationsPageResponse.model_validate(result),
    )


@router.get(
    "/freelancers/me/recommendations/projects",
    response_model=ApiResponse[ProjectRecommendationsPageResponse],
    responses=error_responses(400, 401, 403, 404, 422),
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
) -> SuccessBody[ProjectRecommendationsPageResponse]:
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError(
            "Hanya Freelancer yang dapat meminta "
            "rekomendasi Project"
        )

    data = RecommendProjectsInput(
        freelancer_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )

    result = use_case.execute(data)

    return success_response(
        "Rekomendasi project berhasil diambil",
        ProjectRecommendationsPageResponse.model_validate(result),
    )
