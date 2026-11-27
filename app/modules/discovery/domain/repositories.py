from typing import Protocol

from app.modules.discovery.domain.entities import (
    FreelancerDetail,
    FreelancerSearchFilters,
    FreelancerSummary,
)


class DiscoveryRepository(Protocol):
    def search_freelancers(
        self,
        filters: FreelancerSearchFilters,
        limit: int,
        offset: int,
    ) -> list[FreelancerSummary]:
        ...

    def get_freelancer_detail(
        self,
        freelancer_id: str,
    ) -> FreelancerDetail | None:
        ...
