
from dataclasses import dataclass

from app.modules.matching.domain.entities import (
    FreelancerRecommendation,
    ProjectRecommendation,
)


# ============================================================
# 1. RECOMMEND FREELANCERS INPUT
# ============================================================

@dataclass(frozen=True, slots=True)
class RecommendFreelancersInput:
    """
    Input rekomendasi Freelancer untuk UMKM.

    umkm_id wajib berasal dari identitas
    pengguna yang sudah terautentikasi.
    """

    project_id: str
    umkm_id: str

    limit: int = 20
    offset: int = 0


# ============================================================
# 2. RECOMMEND PROJECTS INPUT
# ============================================================

@dataclass(frozen=True, slots=True)
class RecommendProjectsInput:
    """
    Input rekomendasi Project untuk Freelancer.

    freelancer_id wajib berasal dari identitas
    pengguna yang sudah terautentikasi.
    """

    freelancer_id: str

    limit: int = 20
    offset: int = 0


# ============================================================
# 3. FREELANCER RECOMMENDATIONS PAGE
# ============================================================

@dataclass(frozen=True, slots=True)
class FreelancerRecommendationsPage:
    """
    Hasil rekomendasi Freelancer untuk project.
    """

    project_id: str
    items: tuple[FreelancerRecommendation, ...]

    limit: int
    offset: int
    has_more: bool


# ============================================================
# 4. PROJECT RECOMMENDATIONS PAGE
# ============================================================

@dataclass(frozen=True, slots=True)
class ProjectRecommendationsPage:
    """
    Hasil rekomendasi project untuk Freelancer.
    """

    freelancer_id: str
    items: tuple[ProjectRecommendation, ...]

    limit: int
    offset: int
    has_more: bool