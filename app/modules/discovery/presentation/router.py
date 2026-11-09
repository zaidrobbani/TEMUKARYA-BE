from fastapi import APIRouter, Depends, Query
from fastapi import status

from app.core.exceptions import ForbiddenError

from app.modules.users.domain.entities import UserRole

from app.modules.discovery.application.dto import (
    SearchFreelancersInput,
)

from app.modules.discovery.application.use_cases import (
    GetFreelancerDetail,
    SearchFreelancers,
)

from app.modules.discovery.presentation.dependencies import (
    AuthenticatedDiscoveryUser,
    get_authenticated_discovery_user,
    get_freelancer_detail_use_case,
    get_search_freelancers_use_case,
)

from app.modules.discovery.presentation.schemas import (
    FreelancerDetailResponse,
    FreelancersPageResponse,
    FreelancerSummaryResponse,
)


# ============================================================
# DISCOVERY ROUTER
# ============================================================

router = APIRouter(
    prefix="/freelancers",
    tags=["discovery"],
)


# ============================================================
# 1. SEARCH & FILTER FREELANCERS
# ============================================================

@router.get(
    "",
    response_model=FreelancersPageResponse,
    status_code=status.HTTP_200_OK,
    summary="Search Freelancers",
    description=(
        "UMKM dapat mencari Freelancer berdasarkan "
        "nama, profesi, skill, kota, harga jasa, "
        "pengalaman, dan rating."
    ),
)
def search_freelancers(
    search: str | None = Query(
        default=None,
        max_length=100,
    ),

    skill_ids: list[str] | None = Query(
        default=None,
        description=(
            "Daftar skill ID. Kirim parameter "
            "skill_ids berulang untuk banyak skill."
        ),
    ),

    city: str | None = Query(
        default=None,
        max_length=100,
    ),

    availability_status: str = Query(
        default="AVAILABLE",
        max_length=25,
        description=(
            "AVAILABLE, BUSY, atau ALL "
            "untuk menampilkan seluruh status."
        ),
    ),

    min_price: int | None = Query(
        default=None,
        ge=0,
        le=(2**64) - 1,
    ),

    max_price: int | None = Query(
        default=None,
        ge=0,
        le=(2**64) - 1,
    ),

    min_experience_count: int | None = Query(
        default=None,
        ge=0,
    ),

    min_rating: float | None = Query(
        default=None,
        ge=0,
        le=5,
        allow_inf_nan=False,
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

    current_user: AuthenticatedDiscoveryUser = Depends(
        get_authenticated_discovery_user
    ),

    use_case: SearchFreelancers = Depends(
        get_search_freelancers_use_case
    ),
) -> FreelancersPageResponse:

    # ========================================================
    # 1. ROLE AUTHORIZATION
    # ========================================================

    if current_user.role != UserRole.UMKM:
        raise ForbiddenError(
            "Hanya UMKM yang dapat mencari Freelancer"
        )

    # ========================================================
    # 2. NORMALIZE AVAILABILITY STATUS
    # ========================================================

    normalized_availability = (
        availability_status.strip().upper()
    )

    if normalized_availability == "ALL":
        normalized_availability = None

    elif normalized_availability not in (
        "AVAILABLE",
        "BUSY",
    ):
        from app.core.exceptions import BadRequestError

        raise BadRequestError(
            "Availability status harus AVAILABLE, "
            "BUSY, atau ALL"
        )

    # ========================================================
    # 3. BUILD APPLICATION INPUT
    # ========================================================

    data = SearchFreelancersInput(
        search=search,
        skill_ids=tuple(
            skill_ids or ()
        ),
        city=city,
        availability_status=(
            normalized_availability
        ),
        min_price=min_price,
        max_price=max_price,
        min_experience_count=(
            min_experience_count
        ),
        min_rating=min_rating,
        limit=limit,
        offset=offset,
    )

    # ========================================================
    # 4. EXECUTE USE CASE
    # ========================================================

    page = use_case.execute(data)

    # ========================================================
    # 5. BUILD HTTP RESPONSE
    # ========================================================

    return FreelancersPageResponse(
        items=[
            FreelancerSummaryResponse.model_validate(
                freelancer
            )
            for freelancer in page.items
        ],
        limit=page.limit,
        offset=page.offset,
        has_more=page.has_more,
    )


# ============================================================
# 2. GET FREELANCER DETAIL
# ============================================================

@router.get(
    "/{freelancer_id}",
    response_model=FreelancerDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Freelancer Detail",
    description=(
        "UMKM melihat profil profesional, skill, "
        "pengalaman kerja, portofolio, rating, "
        "dan review Freelancer."
    ),
)
def get_freelancer_detail(
    freelancer_id: str,

    current_user: AuthenticatedDiscoveryUser = Depends(
        get_authenticated_discovery_user
    ),

    use_case: GetFreelancerDetail = Depends(
        get_freelancer_detail_use_case
    ),
) -> FreelancerDetailResponse:

    # ========================================================
    # 1. ROLE AUTHORIZATION
    # ========================================================

    if current_user.role != UserRole.UMKM:
        raise ForbiddenError(
            "Hanya UMKM yang dapat melihat "
            "detail Freelancer"
        )

    # ========================================================
    # 2. EXECUTE USE CASE
    # ========================================================

    freelancer = use_case.execute(
        freelancer_id=freelancer_id
    )

    # ========================================================
    # 3. BUILD HTTP RESPONSE
    # ========================================================

    return FreelancerDetailResponse.model_validate(
        freelancer
    )