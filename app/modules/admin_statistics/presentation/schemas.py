from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.core.responses import UtcDateTime


class AdminResponseBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )


class AdminUserResponse(AdminResponseBase):
    id: str
    name: str
    email: str
    role: str
    created_at: UtcDateTime


class AdminUserPageResponse(AdminResponseBase):
    items: list[AdminUserResponse]

    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class AdminUMKMProfileResponse(AdminResponseBase):
    business_name: str
    business_category: str
    business_address: str
    city: str


class AdminFreelancerProfileResponse(AdminResponseBase):
    professional_title: str
    bio: str | None
    city: str

    service_price_min: int | None
    service_price_max: int | None

    availability_status: str


class AdminUserDetailResponse(AdminResponseBase):
    user: AdminUserResponse

    umkm_profile: (
        AdminUMKMProfileResponse | None
    ) = None

    freelancer_profile: (
        AdminFreelancerProfileResponse | None
    ) = None


class AdminProjectResponse(AdminResponseBase):
    id: str
    title: str
    category_id: str

    umkm_id: str
    umkm_name: str | None

    assigned_freelancer_id: str | None
    assigned_freelancer_name: str | None

    budget: int = Field(ge=0)
    deadline: date
    status: str

    created_at: UtcDateTime


class AdminProjectPageResponse(AdminResponseBase):
    items: list[AdminProjectResponse]

    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class AdminProjectDetailResponse(AdminResponseBase):
    project: AdminProjectResponse

    description: str

    agreed_price: int | None = Field(
        default=None,
        ge=0,
    )

    published_at: UtcDateTime | None
    started_at: UtcDateTime | None
    completed_at: UtcDateTime | None


class AdminSystemStatisticsResponse(
    AdminResponseBase
):
    total_umkm: int = Field(ge=0)
    total_freelancers: int = Field(ge=0)

    total_projects: int = Field(ge=0)
    completed_projects: int = Field(ge=0)

    total_transactions: int = Field(ge=0)
    platform_income: int = Field(ge=0)
