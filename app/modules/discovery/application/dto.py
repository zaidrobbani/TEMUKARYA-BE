
from dataclasses import dataclass

from app.modules.discovery.domain.entities import (
    FreelancerSummary,
)


# ============================================================
# SEARCH FREELANCERS INPUT
# ============================================================

@dataclass(frozen=True)
class SearchFreelancersInput:
    """
    Input pencarian Freelancer dari Presentation Layer.

    Semua filter bersifat opsional.
    Secara default hanya menampilkan
    Freelancer dengan status AVAILABLE.
    """

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


# ============================================================
# SEARCH FREELANCERS RESULT
# ============================================================

@dataclass(frozen=True)
class FreelancersPage:
    """
    Hasil pencarian Freelancer dengan pagination.
    """

    items: tuple[FreelancerSummary, ...]
    limit: int
    offset: int
    has_more: bool