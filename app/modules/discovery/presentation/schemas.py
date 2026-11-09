from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.core.responses import UtcDateTime


# ============================================================
# PUBLIC SKILL RESPONSE
# ============================================================

class FreelancerSkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


# ============================================================
# PUBLIC EXPERIENCE RESPONSE
# ============================================================

class FreelancerExperienceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_title: str
    organization_name: str
    description: str
    start_date: date
    end_date: date | None = None


# ============================================================
# PUBLIC PORTFOLIO RESPONSE
# ============================================================

class FreelancerPortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    project_url: str | None = None


# ============================================================
# PUBLIC REVIEW RESPONSE
# ============================================================

class FreelancerReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    rating: int = Field(ge=1, le=5)
    review_text: str | None = None
    created_at: UtcDateTime | None = None


# ============================================================
# FREELANCER SUMMARY RESPONSE
# ============================================================

class FreelancerSummaryResponse(BaseModel):
    """
    Response untuk hasil pencarian Freelancer.

    Hanya field publik yang diizinkan.
    Email, password_hash, dan data autentikasi
    tidak dimasukkan.
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    name: str
    professional_title: str
    city: str
    availability_status: str

    service_price_min: int | None = None
    service_price_max: int | None = None

    skills: list[FreelancerSkillResponse] = Field(
        default_factory=list
    )

    experience_count: int = 0
    average_rating: float | None = None
    review_count: int = 0


# ============================================================
# FREELANCER DETAIL RESPONSE
# ============================================================

class FreelancerDetailResponse(
    FreelancerSummaryResponse
):
    """
    Detail profil Freelancer yang dapat
    dilihat oleh UMKM.
    """

    bio: str | None = None

    experiences: list[
        FreelancerExperienceResponse
    ] = Field(default_factory=list)

    portfolios: list[
        FreelancerPortfolioResponse
    ] = Field(default_factory=list)

    reviews: list[
        FreelancerReviewResponse
    ] = Field(default_factory=list)


# ============================================================
# FREELANCER SEARCH PAGE RESPONSE
# ============================================================

class FreelancersPageResponse(BaseModel):
    items: list[FreelancerSummaryResponse]
    limit: int
    offset: int
    has_more: bool