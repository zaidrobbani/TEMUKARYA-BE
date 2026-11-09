
from fastapi import APIRouter, Depends, Query, status

from app.core.exceptions import ForbiddenError

from app.modules.users.domain.entities import UserRole

from app.modules.applications.application.dto import (
    SubmitApplicationInput,
)

from app.modules.applications.application.use_cases import (
    GetMyApplications,
    GetProjectApplicants,
    SubmitApplication,
)

from app.modules.applications.presentation.dependencies import (
    AuthenticatedApplicationUser,
    get_authenticated_application_user,
    get_my_applications_use_case,
    get_project_applicants_use_case,
    get_submit_application_use_case,
)

from app.modules.applications.presentation.schemas import (
    ApplicationResponse,
    ApplicationsPageResponse,
    SubmitApplicationRequest,
)


# ============================================================
# ROUTER CONFIGURATION
# ============================================================

router = APIRouter(
    tags=["applications"],
)


# ============================================================
# 1. SUBMIT PROJECT APPLICATION
# ============================================================

@router.post(
    "/projects/{project_id}/applications",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Project Application",
    description=(
        "Freelancer mengirim proposal untuk proyek "
        "yang telah dipublikasikan dan masih terbuka."
    ),
)
def submit_project_application(
    project_id: str,
    body: SubmitApplicationRequest,
    current_user: AuthenticatedApplicationUser = Depends(
        get_authenticated_application_user
    ),
    use_case: SubmitApplication = Depends(
        get_submit_application_use_case
    ),
) -> ApplicationResponse:

    # ========================================================
    # 1. AUTHORIZATION
    # ========================================================

    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError(
            "Hanya Freelancer yang dapat melamar proyek"
        )

    # ========================================================
    # 2. CONVERT REQUEST TO APPLICATION DTO
    # ========================================================

    data = SubmitApplicationInput(
        proposed_price=body.proposed_price,
        estimated_duration_days=body.estimated_duration_days,
        proposal_message=body.proposal_message,
    )

    # ========================================================
    # 3. EXECUTE APPLICATION USE CASE
    # ========================================================

    application = use_case.execute(
        freelancer_id=current_user.user_id,
        project_id=project_id,
        data=data,
    )

    return ApplicationResponse.model_validate(
        application
    )


# ============================================================
# 2. GET MY APPLICATIONS
# ============================================================

@router.get(
    "/applications/mine",
    response_model=ApplicationsPageResponse,
    status_code=status.HTTP_200_OK,
    summary="Get My Applications",
    description=(
        "Freelancer melihat daftar lamaran "
        "yang pernah dikirim beserta statusnya."
    ),
)
def get_my_applications(
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
    current_user: AuthenticatedApplicationUser = Depends(
        get_authenticated_application_user
    ),
    use_case: GetMyApplications = Depends(
        get_my_applications_use_case
    ),
) -> ApplicationsPageResponse:

    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError(
            "Hanya Freelancer yang dapat melihat "
            "daftar lamarannya"
        )

    result = use_case.execute(
        freelancer_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )

    return ApplicationsPageResponse(
        items=[
            ApplicationResponse.model_validate(item)
            for item in result.items
        ],
        limit=result.limit,
        offset=result.offset,
        has_more=result.has_more,
    )


# ============================================================
# 3. GET PROJECT APPLICANTS
# ============================================================

@router.get(
    "/projects/{project_id}/applications",
    response_model=ApplicationsPageResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Project Applicants",
    description=(
        "UMKM melihat daftar Freelancer yang "
        "melamar proyek miliknya."
    ),
)
def get_project_applicants(
    project_id: str,
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
    current_user: AuthenticatedApplicationUser = Depends(
        get_authenticated_application_user
    ),
    use_case: GetProjectApplicants = Depends(
        get_project_applicants_use_case
    ),
) -> ApplicationsPageResponse:

    if current_user.role != UserRole.UMKM:
        raise ForbiddenError(
            "Hanya UMKM yang dapat melihat "
            "daftar pelamar proyek"
        )

    result = use_case.execute(
        umkm_id=current_user.user_id,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )

    return ApplicationsPageResponse(
        items=[
            ApplicationResponse.model_validate(item)
            for item in result.items
        ],
        limit=result.limit,
        offset=result.offset,
        has_more=result.has_more,
    )
