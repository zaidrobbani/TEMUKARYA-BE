from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProjectMatchingSource:
    project_id: str
    umkm_id: str
    title: str
    category_id: str
    status: str

    required_skill_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FreelancerMatchingSource:
    freelancer_id: str
    name: str
    professional_title: str
    city: str
    availability_status: str

    skill_ids: tuple[str, ...] = ()

    service_price_min: int | None = None
    service_price_max: int | None = None


@dataclass(frozen=True, slots=True)
class SkillMatchResult:
    score_percent: float
    required_count: int
    matched_count: int

    matched_skill_ids: tuple[str, ...]
    missing_skill_ids: tuple[str, ...]

    meets_threshold: bool


@dataclass(frozen=True, slots=True)
class FreelancerRecommendation:
    freelancer: FreelancerMatchingSource
    match: SkillMatchResult


@dataclass(frozen=True, slots=True)
class ProjectRecommendation:
    project: ProjectMatchingSource
    match: SkillMatchResult
