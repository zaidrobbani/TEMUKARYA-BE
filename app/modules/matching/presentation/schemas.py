
from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 1. MATCHING SCORE RESPONSE
# ============================================================

class SkillMatchResponse(BaseModel):
    """
    Hasil perhitungan kecocokan skill.

    Contoh:
    3 dari 5 skill cocok = 60%.
    """

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


# ============================================================
# 2. FREELANCER MATCHING SOURCE RESPONSE
# ============================================================

class FreelancerMatchingSourceResponse(BaseModel):
    """
    Informasi publik Freelancer
    yang direkomendasikan kepada UMKM.

    Tidak menampilkan email, password_hash,
    atau informasi autentikasi lainnya.
    """

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


# ============================================================
# 3. PROJECT MATCHING SOURCE RESPONSE
# ============================================================

class ProjectMatchingSourceResponse(BaseModel):
    """
    Informasi project yang direkomendasikan
    kepada Freelancer.
    """

    model_config = ConfigDict(from_attributes=True)

    project_id: str
    umkm_id: str
    title: str
    category_id: str
    status: str

    required_skill_ids: list[str]


# ============================================================
# 4. FREELANCER RECOMMENDATION RESPONSE
# ============================================================

class FreelancerRecommendationResponse(BaseModel):
    """
    Satu Freelancer beserta skor matching-nya.
    """

    model_config = ConfigDict(from_attributes=True)

    freelancer: FreelancerMatchingSourceResponse
    match: SkillMatchResponse


# ============================================================
# 5. PROJECT RECOMMENDATION RESPONSE
# ============================================================

class ProjectRecommendationResponse(BaseModel):
    """
    Satu Project beserta skor matching-nya.
    """

    model_config = ConfigDict(from_attributes=True)

    project: ProjectMatchingSourceResponse
    match: SkillMatchResponse


# ============================================================
# 6. FREELANCER RECOMMENDATIONS PAGE
# ============================================================

class FreelancerRecommendationsPageResponse(BaseModel):
    """
    Halaman rekomendasi Freelancer untuk UMKM.
    """

    model_config = ConfigDict(from_attributes=True)

    project_id: str

    items: list[FreelancerRecommendationResponse]

    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: bool


# ============================================================
# 7. PROJECT RECOMMENDATIONS PAGE
# ============================================================

class ProjectRecommendationsPageResponse(BaseModel):
    """
    Halaman rekomendasi Project untuk Freelancer.
    """

    model_config = ConfigDict(from_attributes=True)

    freelancer_id: str

    items: list[ProjectRecommendationResponse]

    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_more: bool