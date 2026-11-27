from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.modules.milestones.domain.entities import (
    Milestone,
)


@dataclass(frozen=True, slots=True)
class ProjectMilestoneContext:
    project_id: str
    umkm_id: str
    status: str
    started_at: datetime | None
    deadline: date

    freelancer_id: str | None = None


class MilestoneRepository(Protocol):
    def get_project_context(
        self,
        project_id: str,
    ) -> ProjectMilestoneContext | None:
        ...

    def list_milestones(
        self,
        project_id: str,
    ) -> tuple[Milestone, ...]:
        ...

    def get_total_weight(
        self,
        project_id: str,
    ) -> Decimal:
        ...

    def replace_plan_and_reset_approvals(
        self,
        project_id: str,
        milestones: tuple[Milestone, ...],
    ) -> None:
        ...

    def complete_if_pending(
        self,
        project_id: str,
        milestone_id: str,
        updated_by_user_id: str,
        completed_at: datetime,
    ) -> bool:
        ...
