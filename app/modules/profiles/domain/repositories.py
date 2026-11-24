from typing import Protocol

from app.modules.profiles.domain.entities import (
    UmkmProfile,
    FreelancerProfile,
)

from app.modules.profiles.domain.entities import (
    FreelancerExperience,
    Portfolio,
)

class UmkmProfileRepository(Protocol):

    def update(self, profile: UmkmProfile) -> UmkmProfile | None:
        ...

    def get_by_user_id(
        self,
        user_id: str
    ) -> UmkmProfile | None:
        ...

    def add(
        self,
        profile: UmkmProfile
    ) -> UmkmProfile:
        ...


class FreelancerProfileRepository(Protocol):

    def update(self, profile: FreelancerProfile) -> FreelancerProfile | None:
        ...

    def get_by_user_id(
        self,
        user_id: str,
    ) -> FreelancerProfile | None:
        ...

    def add(
        self,
        profile: FreelancerProfile,
    ) -> FreelancerProfile:
        ...


class FreelancerSkillsRepository(Protocol):

    def get_skill_ids(
        self,
        freelancer_id: str,
    ) -> list[str]:
        ...

    def get_existing_skill_ids(
        self,
        skill_ids: list[str],
    ) -> set[str]:
        ...

    def replace_skills(
        self,
        freelancer_id: str,
        skill_ids: list[str],
    ) -> None:
        ...


class FreelancerExperienceRepository(Protocol):

    def list_by_freelancer_id(
        self, freelancer_id: str,
    ) -> list[FreelancerExperience]:
        ...

    def update(self, experience: FreelancerExperience) -> bool:
        """Update hanya jika ID dan freelancer_id cocok; False jika tidak ada."""
        ...

    def delete(self, experience_id: str, freelancer_id: str) -> bool:
        """Delete hanya jika ID dan freelancer_id cocok; False jika tidak ada."""
        ...

    def add(
        self,
        experience: FreelancerExperience,
    ) -> None:
        ...


class PortfolioRepository(Protocol):
    def add(self, portfolio: Portfolio) -> Portfolio:
        ...

    def list_by_freelancer_id(
        self, freelancer_id: str, limit: int, offset: int,
    ) -> list[Portfolio]:
        ...

    def get_by_id(self, portfolio_id: str, freelancer_id: str) -> Portfolio | None:
        ...

    def update(self, portfolio: Portfolio) -> Portfolio | None:
        """Return metadata tersimpan hanya jika ID dan pemilik cocok."""
        ...

    def delete(self, portfolio_id: str, freelancer_id: str) -> bool:
        ...
