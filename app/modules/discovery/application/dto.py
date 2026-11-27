from dataclasses import dataclass

from app.modules.discovery.domain.entities import (
    FreelancerSummary,
)


@dataclass(frozen=True)
class SearchFreelancersInput:
    search: str | None = None
    skill_ids: tuple[str, ...] = ()

    city: str | None = None
    availability_status: str | None = "AVAILABLE"

    min_price: int | None = None
    max_price: int | None = None

    min_experience_count: int | None = None
    min_rating: float | None = None

    limit: int = 20
    offset: int = 0


@dataclass(frozen=True)
class FreelancersPage:
    items: tuple[FreelancerSummary, ...]
    limit: int
    offset: int
    has_more: bool
