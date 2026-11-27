from collections.abc import Iterable
from typing import Protocol

from app.modules.matching.domain.entities import (
    FreelancerMatchingSource,
    ProjectMatchingSource,
)


class MatchingRepository(Protocol):
    def get_project(
        self,
        project_id: str,
    ) -> ProjectMatchingSource | None:
        ...

    def get_freelancer(
        self,
        freelancer_id: str,
    ) -> FreelancerMatchingSource | None:
        ...

    def iter_available_freelancers(
        self,
    ) -> Iterable[FreelancerMatchingSource]:
        ...

    def iter_published_projects(
        self,
    ) -> Iterable[ProjectMatchingSource]:
        ...
