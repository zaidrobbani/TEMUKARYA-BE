from dataclasses import dataclass

from app.modules.applications.domain.entities import (
    ProjectApplication,
)


@dataclass(frozen=True)
class SubmitApplicationInput:
    proposed_price: int
    estimated_duration_days: int
    proposal_message: str


@dataclass(frozen=True)
class ApplicationsPage:
    items: tuple[ProjectApplication, ...]
    limit: int
    offset: int
    has_more: bool
