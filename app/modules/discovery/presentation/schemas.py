from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.core.responses import UtcDateTime


class FreelancerSkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str


class FreelancerExperienceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_title: str
    organization_name: str
    description: str
    start_date: date
    end_date: date | None = None


class FreelancerPortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    project_url: str | None = None
    cover_image_url: str | None = None


class FreelancerReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    rating: int = Field(ge=1, le=5)
    review_text: str | None = None
    created_at: UtcDateTime | None = None


class FreelancerSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    name: str
    profile_image_url: str | None = None
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


class FreelancerDetailResponse(
    FreelancerSummaryResponse
):
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


class FreelancersPageResponse(BaseModel):
    items: list[FreelancerSummaryResponse]
    limit: int
    offset: int
    has_more: bool
