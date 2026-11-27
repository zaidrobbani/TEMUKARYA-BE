from pydantic import BaseModel, ConfigDict, Field


class SkillMatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score_percent: float = Field(
        ge=0,
        le=100,
        allow_inf_nan=False,
    )

    required_count: int = Field(ge=0)
    matched_count: int = Field(ge=0)

    matched_skill_ids: list[str]
    missing_skill_ids: list[str]

    meets_threshold: bool


class FreelancerMatchingSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    freelancer_id: str
    name: str
    professional_title: str
    city: str
    availability_status: str

    skill_ids: list[str]

    service_price_min: int | None = Field(
        default=None,
        ge=0,
    )

    service_price_max: int | None = Field(
        default=None,
        ge=0,
    )


class ProjectMatchingSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    umkm_id: str
    title: str
    category_id: str
    status: str

    required_skill_ids: list[str]


class FreelancerRecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    freelancer: FreelancerMatchingSourceResponse
    match: SkillMatchResponse


class ProjectRecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project: ProjectMatchingSourceResponse
    match: SkillMatchResponse


class FreelancerRecommendationsPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: str

    items: list[FreelancerRecommendationResponse]

    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: bool


class ProjectRecommendationsPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    freelancer_id: str

    items: list[ProjectRecommendationResponse]

    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: bool
