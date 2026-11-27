from abc import ABC, abstractmethod

from app.modules.reviews.domain.entities import FreelancerReview, PublicReview, RatingSummary


class ReviewRepository(ABC):
    @abstractmethod
    def get_by_project(self, project_id: str) -> FreelancerReview | None: ...

    @abstractmethod
    def add(self, review: FreelancerReview) -> None: ...

    @abstractmethod
    def list_for_freelancer(self, freelancer_id: str, limit: int, offset: int) -> list[PublicReview]:
        pass

    @abstractmethod
    def summary_for_freelancer(self, freelancer_id: str) -> RatingSummary: ...
