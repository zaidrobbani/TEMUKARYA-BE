from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.core.responses import UtcDateTime


# ============================================================
# 1. BASE RESPONSE SCHEMA
# ============================================================

class AdminResponseBase(BaseModel):
    """
    Mendukung konversi Domain Dataclass
    menjadi Pydantic Response.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )


# ============================================================
# 2. USER SUMMARY RESPONSE
# ============================================================

class AdminUserResponse(AdminResponseBase):
    """
    Informasi dasar pengguna.

    Tidak menyertakan password_hash.
    """

    id: str
    name: str
    email: str
    role: str
    created_at: UtcDateTime


# ============================================================
# 3. USER LIST RESPONSE
# ============================================================

class AdminUserPageResponse(AdminResponseBase):
    """
    Daftar pengguna dengan metadata pagination.
    """

    items: list[AdminUserResponse]

    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


# ============================================================
# 4. UMKM PROFILE RESPONSE
# ============================================================

class AdminUMKMProfileResponse(AdminResponseBase):
    """
    Informasi UMKM.
    """

    business_name: str
    business_category: str
    business_address: str
    city: str


# ============================================================
# 5. FREELANCER PROFILE RESPONSE
# ============================================================

class AdminFreelancerProfileResponse(AdminResponseBase):
    """
    Informasi Freelancer.
    """

    professional_title: str
    bio: str | None
    city: str

    service_price_min: int | None
    service_price_max: int | None

    availability_status: str


# ============================================================
# 6. USER DETAIL RESPONSE
# ============================================================

class AdminUserDetailResponse(AdminResponseBase):
    """
    Detail User sesuai role.

    UMKM:
        umkm_profile tersedia bila sudah dibuat.

    Freelancer:
        freelancer_profile tersedia bila sudah dibuat.
    """

    user: AdminUserResponse

    umkm_profile: (
        AdminUMKMProfileResponse | None
    ) = None

    freelancer_profile: (
        AdminFreelancerProfileResponse | None
    ) = None


# ============================================================
# 7. PROJECT SUMMARY RESPONSE
# ============================================================

class AdminProjectResponse(AdminResponseBase):
    """
    Ringkasan project untuk daftar Admin.
    """

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


# ============================================================
# 8. PROJECT LIST RESPONSE
# ============================================================

class AdminProjectPageResponse(AdminResponseBase):
    """
    Daftar seluruh project.
    """

    items: list[AdminProjectResponse]

    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


# ============================================================
# 9. PROJECT DETAIL RESPONSE
# ============================================================

class AdminProjectDetailResponse(AdminResponseBase):
    """
    Detail Project untuk Admin.
    """

    project: AdminProjectResponse

    description: str

    agreed_price: int | None = Field(
        default=None,
        ge=0,
    )

    published_at: UtcDateTime | None
    started_at: UtcDateTime | None
    completed_at: UtcDateTime | None


# ============================================================
# 10. SYSTEM STATISTICS RESPONSE
# ============================================================

class AdminSystemStatisticsResponse(
    AdminResponseBase
):
    """
    Statistik sistem TEMUKARYA.

    Income menggunakan integer Rupiah.
    """

    total_umkm: int = Field(ge=0)
    total_freelancers: int = Field(ge=0)

    total_projects: int = Field(ge=0)
    completed_projects: int = Field(ge=0)

    total_transactions: int = Field(ge=0)
    platform_income: int = Field(ge=0)