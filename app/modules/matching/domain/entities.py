
from dataclasses import dataclass


# ============================================================
# 1. PROJECT MATCHING SOURCE
# ============================================================

@dataclass(frozen=True, slots=True)
class ProjectMatchingSource:
    """
    Informasi project yang dibutuhkan
    untuk menghitung kecocokan skill.
    """

    project_id: str
    umkm_id: str
    title: str
    category_id: str
    status: str

    required_skill_ids: tuple[str, ...] = ()


# ============================================================
# 2. FREELANCER MATCHING SOURCE
# ============================================================

@dataclass(frozen=True, slots=True)
class FreelancerMatchingSource:
    """
    Informasi publik Freelancer yang
    diperlukan dalam proses matching.
    """

    freelancer_id: str
    name: str
    professional_title: str
    city: str
    availability_status: str

    skill_ids: tuple[str, ...] = ()

    service_price_min: int | None = None
    service_price_max: int | None = None


# ============================================================
# 3. SKILL MATCH RESULT
# ============================================================

@dataclass(frozen=True, slots=True)
class SkillMatchResult:
    """
    Hasil perhitungan kecocokan skill.

    Belum termasuk pemeriksaan status project,
    ketersediaan Freelancer, dan otorisasi.
    """

    score_percent: float
    required_count: int
    matched_count: int

    matched_skill_ids: tuple[str, ...]
    missing_skill_ids: tuple[str, ...]

    meets_threshold: bool


# ============================================================
# 4. FREELANCER RECOMMENDATION
# ============================================================

@dataclass(frozen=True, slots=True)
class FreelancerRecommendation:
    """
    Hasil rekomendasi Freelancer untuk UMKM.
    """

    freelancer: FreelancerMatchingSource
    match: SkillMatchResult


# ============================================================
# 5. PROJECT RECOMMENDATION
# ============================================================

@dataclass(frozen=True, slots=True)
class ProjectRecommendation:
    """
    Hasil rekomendasi Project untuk Freelancer.
    """

    project: ProjectMatchingSource
    match: SkillMatchResult