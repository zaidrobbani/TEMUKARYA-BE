from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.core.responses import UtcDateTime


class CreateUmkmProfileRequest(BaseModel):
    business_name: str = Field(
        min_length=1,
        max_length=160,
    )

    business_category: str = Field(
        min_length=1,
        max_length=100,
    )

    business_address: str = Field(
        min_length=1,
        max_length=300,
    )

    city: str = Field(
        min_length=1,
        max_length=100,
    )


class UmkmProfileResponse(BaseModel):
    user_id: str
    business_name: str
    business_category: str
    business_address: str
    city: str



class CreateFreelancerProfileRequest(BaseModel):
    professional_title: str = Field(
        min_length=1,
        max_length=150,
    )

    city: str = Field(
        min_length=1,
        max_length=100,
    )

    bio: str | None = None

    service_price_min: int | None = Field(
        default=None,
        ge=0,
        le=18446744073709551615,
    )

    service_price_max: int | None = Field(
        default=None,
        ge=0,
        le=18446744073709551615,
    )


class FreelancerProfileResponse(BaseModel):
    user_id: str
    professional_title: str
    city: str
    bio: str | None
    service_price_min: int | None
    service_price_max: int | None
    availability_status: str


class UpdateUmkmProfileRequest(CreateUmkmProfileRequest):
    """PUT requires all editable fields and rejects identity/audit fields."""

    model_config = ConfigDict(extra="forbid")


class UpdateFreelancerProfileRequest(CreateFreelancerProfileRequest):
    """PUT clears omitted nullable fields; availability must be explicit."""

    model_config = ConfigDict(extra="forbid")
    availability_status: str = Field(min_length=1, max_length=25)
    service_price_min: int | None = Field(default=None, strict=True, ge=0, le=18446744073709551615)
    service_price_max: int | None = Field(default=None, strict=True, ge=0, le=18446744073709551615)


class SetFreelancerSkillsRequest(BaseModel):
    skill_ids: list[str] = Field(
        min_length=0,
        max_length=26,
    )


class FreelancerSkillsResponse(BaseModel):
    freelancer_id: str
    skill_ids: list[str]


# CREATE FREELANCER EXPERIENCE SCHEMAS

class CreateFreelancerExperienceRequest(BaseModel):
    job_title: str = Field(
        min_length=1,
        max_length=150,
    )

    organization_name: str = Field(
        min_length=1,
        max_length=160,
    )

    description: str = Field(
        min_length=1,
    )

    start_date: date

    end_date: date | None = None


class UpdateFreelancerExperienceRequest(CreateFreelancerExperienceRequest):
    # PUT menerima isi experience saja; ID dan ownership tidak dapat diganti.
    model_config = ConfigDict(extra="forbid")


class FreelancerExperienceResponse(BaseModel):
    id: str
    freelancer_id: str
    job_title: str
    organization_name: str
    description: str
    start_date: date
    end_date: date | None


class CreatePortfolioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=180)
    description: str = Field(min_length=1)
    project_url: str | None = Field(
        default=None, max_length=1000,
        description="URL HTTP/HTTPS dengan host, tanpa kredensial; null jika tidak ada.",
    )


class UpdatePortfolioRequest(CreatePortfolioRequest):
    """PUT mengganti seluruh metadata; project_url yang dihilangkan menjadi null."""


class PortfolioResponse(BaseModel):
    id: str
    freelancer_id: str
    title: str
    description: str
    project_url: str | None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class PortfolioPageResponse(BaseModel):
    items: list[PortfolioResponse]
    limit: int
    offset: int
    has_more: bool
