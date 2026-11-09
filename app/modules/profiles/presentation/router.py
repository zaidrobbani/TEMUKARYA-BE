from fastapi import APIRouter, Depends, Query, status

from app.core.exceptions import ServiceUnavailableError
from app.core.responses import ApiResponse, error_responses, success_response
from app.modules.profiles.domain.media import StorageFailure
from app.modules.profiles.presentation.media_router import build_media_router

from app.core.exceptions import ForbiddenError
from app.modules.profiles.application.dto import UpdateUmkmProfileInput, UpdateFreelancerProfileInput
from app.modules.profiles.application.self_profile_use_cases import (
    GetUmkmProfile, GetFreelancerProfile, UpdateUmkmProfile, UpdateFreelancerProfile,
)
from app.modules.profiles.presentation.dependencies import (
    get_umkm_profile_use_case, get_freelancer_profile_use_case,
    update_umkm_profile_use_case, update_freelancer_profile_use_case,
)
from app.modules.profiles.presentation.schemas import UpdateUmkmProfileRequest, UpdateFreelancerProfileRequest
from app.modules.users.domain.entities import UserRole

# Application DTO
from app.modules.profiles.application.dto import (
    CreateUmkmProfileInput,
    CreateFreelancerProfileInput,
    SetFreelancerSkillsInput,
    CreateFreelancerExperienceInput,
    UpdateFreelancerExperienceInput,
    CreatePortfolioInput,
    UpdatePortfolioInput,
)

# Application Use Cases
from app.modules.profiles.application.use_cases import (
    CreateUmkmProfile,
    CreateFreelancerProfile,
    SetFreelancerSkills,
    GetFreelancerSkills,
    CreateFreelancerExperience,
    GetFreelancerExperiences,
    UpdateFreelancerExperience,
    DeleteFreelancerExperience,
    CreatePortfolio, GetPortfolios, GetPortfolio, UpdatePortfolio, DeletePortfolio,
)

# Authentication
from app.modules.profiles.presentation.auth import (
    AuthenticatedProfileUser,
    get_authenticated_profile_user,
)

# Dependency Injection
from app.modules.profiles.presentation.dependencies import (
    create_umkm_profile_use_case,
    create_freelancer_profile_use_case,
    set_freelancer_skills_use_case,
    get_freelancer_skills_use_case,
    create_freelancer_experience_use_case,
    get_freelancer_experiences_use_case,
    update_freelancer_experience_use_case,
    delete_freelancer_experience_use_case,
    create_portfolio_use_case, get_portfolios_use_case, get_portfolio_use_case,
    update_portfolio_use_case, delete_portfolio_use_case,
    get_media_service,
)

# Pydantic Schemas
from app.modules.profiles.presentation.schemas import (
    CreateUmkmProfileRequest,
    UmkmProfileResponse,
    CreateFreelancerProfileRequest,
    FreelancerProfileResponse,
    SetFreelancerSkillsRequest,
    FreelancerSkillsResponse,
    CreateFreelancerExperienceRequest,
    FreelancerExperienceResponse,
    UpdateFreelancerExperienceRequest,
    CreatePortfolioRequest, UpdatePortfolioRequest, PortfolioResponse, PortfolioPageResponse,
)


router = APIRouter(
    prefix="/profiles",
    tags=["profiles"],
)


# 1. CREATE UMKM PROFILE
@router.post(
    "/umkm",
    response_model=ApiResponse[UmkmProfileResponse],
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(401, 403, 409, 422),
)
def create_umkm_profile(
    body: CreateUmkmProfileRequest,
    current_user: AuthenticatedProfileUser = Depends(
        get_authenticated_profile_user
    ),
    use_case: CreateUmkmProfile = Depends(
        create_umkm_profile_use_case
    ),
):
    if current_user.role != UserRole.UMKM:
        raise ForbiddenError(
            "Hanya pengguna UMKM yang dapat membuat profil UMKM"
        )

    profile = use_case.execute(
        user_id=current_user.user_id,
        data=CreateUmkmProfileInput(**body.model_dump()),
    )
    return success_response("Profil UMKM berhasil dibuat", profile)


# 2. CREATE FREELANCER PROFILE
@router.post(
    "/freelancer",
    response_model=ApiResponse[FreelancerProfileResponse],
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 403, 409, 422),
)
def create_freelancer_profile(
    body: CreateFreelancerProfileRequest,
    current_user: AuthenticatedProfileUser = Depends(
        get_authenticated_profile_user
    ),
    use_case: CreateFreelancerProfile = Depends(
        create_freelancer_profile_use_case
    ),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError(
            "Hanya Freelancer yang dapat membuat profil Freelancer"
        )

    profile = use_case.execute(
        user_id=current_user.user_id,
        data=CreateFreelancerProfileInput(**body.model_dump()),
    )
    return success_response("Profil Freelancer berhasil dibuat", profile)


@router.get("/umkm/me", response_model=ApiResponse[UmkmProfileResponse], responses=error_responses(401, 403, 404))
def get_my_umkm_profile(
    current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
    use_case: GetUmkmProfile = Depends(get_umkm_profile_use_case),
):
    if current_user.role != UserRole.UMKM:
        raise ForbiddenError("Hanya pengguna UMKM yang dapat membaca profil UMKM")
    return success_response("Profil UMKM berhasil diambil", use_case.execute(user_id=current_user.user_id))


@router.put(
    "/umkm/me",
    response_model=ApiResponse[UmkmProfileResponse],
    responses=error_responses(400, 401, 403, 404, 422),
)
def update_my_umkm_profile(
    body: UpdateUmkmProfileRequest,
    current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
    use_case: UpdateUmkmProfile = Depends(update_umkm_profile_use_case),
):
    if current_user.role != UserRole.UMKM:
        raise ForbiddenError("Hanya pengguna UMKM yang dapat mengubah profil UMKM")
    profile = use_case.execute(user_id=current_user.user_id, data=UpdateUmkmProfileInput(**body.model_dump()))
    return success_response("Profil UMKM berhasil diperbarui", profile)


@router.get(
    "/freelancer/me",
    response_model=ApiResponse[FreelancerProfileResponse],
    responses=error_responses(401, 403, 404),
)
def get_my_freelancer_profile(
    current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
    use_case: GetFreelancerProfile = Depends(get_freelancer_profile_use_case),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError("Hanya Freelancer yang dapat membaca profil Freelancer")
    return success_response("Profil Freelancer berhasil diambil", use_case.execute(user_id=current_user.user_id))


@router.put(
    "/freelancer/me",
    response_model=ApiResponse[FreelancerProfileResponse],
    responses=error_responses(400, 401, 403, 404, 422),
)
def update_my_freelancer_profile(
    body: UpdateFreelancerProfileRequest,
    current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
    use_case: UpdateFreelancerProfile = Depends(update_freelancer_profile_use_case),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError("Hanya Freelancer yang dapat mengubah profil Freelancer")
    profile = use_case.execute(user_id=current_user.user_id, data=UpdateFreelancerProfileInput(**body.model_dump()))
    return success_response("Profil Freelancer berhasil diperbarui", profile)


# 3. UPDATE FREELANCER SKILLS
@router.put(
    "/freelancer/skills",
    response_model=ApiResponse[FreelancerSkillsResponse],
    responses=error_responses(400, 401, 403, 404, 422),
)
def update_freelancer_skills(
    body: SetFreelancerSkillsRequest,
    current_user: AuthenticatedProfileUser = Depends(
        get_authenticated_profile_user
    ),
    use_case: SetFreelancerSkills = Depends(
        set_freelancer_skills_use_case
    ),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError(
            "Hanya Freelancer yang dapat mengubah keahlian"
        )

    skill_ids = use_case.execute(
        freelancer_id=current_user.user_id,
        data=SetFreelancerSkillsInput(
            skill_ids=body.skill_ids
        ),
    )

    return success_response(
        "Keahlian Freelancer berhasil diperbarui",
        FreelancerSkillsResponse(freelancer_id=current_user.user_id, skill_ids=skill_ids),
    )


# 4. GET FREELANCER SKILLS
@router.get(
    "/freelancer/skills",
    response_model=ApiResponse[FreelancerSkillsResponse],
    responses=error_responses(401, 403, 404),
)
def get_freelancer_skills(
    current_user: AuthenticatedProfileUser = Depends(
        get_authenticated_profile_user
    ),
    use_case: GetFreelancerSkills = Depends(
        get_freelancer_skills_use_case
    ),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError(
            "Hanya Freelancer yang dapat melihat keahliannya"
        )

    skill_ids = use_case.execute(
        freelancer_id=current_user.user_id
    )

    return success_response(
        "Keahlian Freelancer berhasil diambil",
        FreelancerSkillsResponse(freelancer_id=current_user.user_id, skill_ids=skill_ids),
    )


# 5. CREATE FREELANCER EXPERIENCE
@router.post(
    "/freelancer/experiences",
    response_model=ApiResponse[FreelancerExperienceResponse],
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 403, 404, 422),
)
def create_freelancer_experience(
    body: CreateFreelancerExperienceRequest,
    current_user: AuthenticatedProfileUser = Depends(
        get_authenticated_profile_user
    ),
    use_case: CreateFreelancerExperience = Depends(
        create_freelancer_experience_use_case
    ),
):
    # 1. Pastikan pengguna memiliki role Freelancer
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError(
            "Hanya Freelancer yang dapat menambahkan pengalaman kerja"
        )

    # 2. Jalankan Use Case CreateFreelancerExperience
    experience = use_case.execute(
        freelancer_id=current_user.user_id,
        data=CreateFreelancerExperienceInput(
            **body.model_dump()
        ),
    )

    # 3. Kembalikan data pengalaman yang berhasil dibuat
    return success_response(
        "Pengalaman kerja berhasil ditambahkan",
        FreelancerExperienceResponse(
            id=experience.id,
            freelancer_id=experience.freelancer_id,
            job_title=experience.job_title,
            organization_name=experience.organization_name,
            description=experience.description,
            start_date=experience.start_date,
            end_date=experience.end_date,
        ),
    )


@router.get(
    "/freelancer/experiences",
    response_model=ApiResponse[list[FreelancerExperienceResponse]],
    responses=error_responses(401, 403),
)
def get_freelancer_experiences(
    current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
    use_case: GetFreelancerExperiences = Depends(get_freelancer_experiences_use_case),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError("Hanya Freelancer yang dapat melihat pengalaman kerja")

    return success_response(
        "Daftar pengalaman kerja berhasil diambil",
        use_case.execute(freelancer_id=current_user.user_id),
    )


@router.put(
    "/freelancer/experiences/{experience_id}",
    response_model=ApiResponse[FreelancerExperienceResponse],
    responses=error_responses(400, 401, 403, 404, 422),
)
def update_freelancer_experience(
    experience_id: str,
    body: UpdateFreelancerExperienceRequest,
    current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
    use_case: UpdateFreelancerExperience = Depends(update_freelancer_experience_use_case),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError("Hanya Freelancer yang dapat mengubah pengalaman kerja")

    experience = use_case.execute(
        freelancer_id=current_user.user_id,
        experience_id=experience_id,
        data=UpdateFreelancerExperienceInput(**body.model_dump()),
    )
    return success_response("Pengalaman kerja berhasil diperbarui", experience)


@router.delete(
    "/freelancer/experiences/{experience_id}",
    response_model=ApiResponse[None],
    responses=error_responses(401, 403, 404),
)
def delete_freelancer_experience(
    experience_id: str,
    current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
    use_case: DeleteFreelancerExperience = Depends(delete_freelancer_experience_use_case),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError("Hanya Freelancer yang dapat menghapus pengalaman kerja")

    use_case.execute(
        freelancer_id=current_user.user_id,
        experience_id=experience_id,
    )
    return success_response("Pengalaman kerja berhasil dihapus")


@router.post(
    "/freelancer/portfolios",
    response_model=ApiResponse[PortfolioResponse],
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 403, 404, 422),
)
def create_portfolio(
    body: CreatePortfolioRequest,
    current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
    use_case: CreatePortfolio = Depends(create_portfolio_use_case),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError("Hanya Freelancer yang dapat membuat portfolio")
    portfolio = use_case.execute(
        freelancer_id=current_user.user_id, data=CreatePortfolioInput(**body.model_dump()),
    )
    return success_response("Portfolio berhasil dibuat", portfolio)


@router.get(
    "/freelancer/portfolios",
    response_model=ApiResponse[PortfolioPageResponse],
    responses=error_responses(400, 401, 403, 422),
)
def get_portfolios(
    current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
    use_case: GetPortfolios = Depends(get_portfolios_use_case),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError("Hanya Freelancer yang dapat melihat portfolio")
    page = use_case.execute(freelancer_id=current_user.user_id, limit=limit, offset=offset)
    return success_response("Daftar portfolio berhasil diambil", page)


@router.get(
    "/freelancer/portfolios/{portfolio_id}",
    response_model=ApiResponse[PortfolioResponse],
    responses=error_responses(401, 403, 404),
)
def get_portfolio(
    portfolio_id: str,
    current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
    use_case: GetPortfolio = Depends(get_portfolio_use_case),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError("Hanya Freelancer yang dapat melihat portfolio")
    portfolio = use_case.execute(freelancer_id=current_user.user_id, portfolio_id=portfolio_id)
    return success_response("Portfolio berhasil diambil", portfolio)


@router.put(
    "/freelancer/portfolios/{portfolio_id}",
    response_model=ApiResponse[PortfolioResponse],
    responses=error_responses(400, 401, 403, 404, 422),
)
def update_portfolio(
    portfolio_id: str,
    body: UpdatePortfolioRequest,
    current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
    use_case: UpdatePortfolio = Depends(update_portfolio_use_case),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError("Hanya Freelancer yang dapat mengubah portfolio")
    portfolio = use_case.execute(
        freelancer_id=current_user.user_id, portfolio_id=portfolio_id,
        data=UpdatePortfolioInput(**body.model_dump()),
    )
    return success_response("Portfolio berhasil diperbarui", portfolio)


@router.delete(
    "/freelancer/portfolios/{portfolio_id}",
    response_model=ApiResponse[None],
    responses=error_responses(401, 403, 404, 503),
)
def delete_portfolio(
    portfolio_id: str,
    current_user: AuthenticatedProfileUser = Depends(get_authenticated_profile_user),
    use_case: DeletePortfolio = Depends(delete_portfolio_use_case),
):
    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError("Hanya Freelancer yang dapat menghapus portfolio")
    try:
        use_case.execute(freelancer_id=current_user.user_id, portfolio_id=portfolio_id)
    except StorageFailure as exc:
        raise ServiceUnavailableError(str(exc)) from exc
    return success_response("Portfolio berhasil dihapus")


router.include_router(build_media_router(get_media_service))
