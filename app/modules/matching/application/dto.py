from dataclasses import dataclass

from app.modules.matching.domain.entities import (
    FreelancerRecommendation,
    ProjectRecommendation,
)


@dataclass(frozen=True, slots=True)
class RecommendFreelancersInput:
    project_id: str
    umkm_id: str

    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class RecommendProjectsInput:
    freelancer_id: str

    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class FreelancerRecommendationsPage:
    project_id: str
    items: tuple[FreelancerRecommendation, ...]

    limit: int
    offset: int
    has_more: bool


@dataclass(frozen=True, slots=True)
class ProjectRecommendationsPage:
    freelancer_id: str
    items: tuple[ProjectRecommendation, ...]

    limit: int
    offset: int
    has_more: bool
