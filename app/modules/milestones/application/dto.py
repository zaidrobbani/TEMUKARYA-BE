from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.modules.milestones.domain.entities import (
    Milestone,
)


@dataclass(frozen=True, slots=True)
class MilestoneActor:
    user_id: str
    role: str


@dataclass(frozen=True, slots=True)
class MilestoneDraft:
    name: str
    description: str
    weight_percent: Decimal
    sort_order: int


@dataclass(frozen=True, slots=True)
class GetMilestonePlanInput:
    project_id: str
    actor: MilestoneActor


@dataclass(frozen=True, slots=True)
class ReplaceMilestonePlanInput:
    project_id: str
    actor: MilestoneActor
    items: tuple[MilestoneDraft, ...]


@dataclass(frozen=True, slots=True)
class CompleteMilestoneInput:
    project_id: str
    milestone_id: str
    actor: MilestoneActor


@dataclass(frozen=True, slots=True)
class GetDelayRiskInput:
    project_id: str
    actor: MilestoneActor
    today: date


@dataclass(frozen=True, slots=True)
class MilestonePlanResult:
    project_id: str
    items: tuple[Milestone, ...]
    total_weight: Decimal
    is_plan_complete: bool
