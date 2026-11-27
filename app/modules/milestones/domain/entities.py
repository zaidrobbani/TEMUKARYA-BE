from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class MilestoneStatus(StrEnum):
    BELUM_SELESAI = "BELUM_SELESAI"
    SELESAI = "SELESAI"


@dataclass(frozen=True, slots=True)
class Milestone:
    id: str
    project_id: str
    name: str
    description: str
    weight_percent: Decimal
    status: MilestoneStatus
    sort_order: int

    completed_at: datetime | None = None
    updated_by_user_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectSchedule:
    project_id: str
    started_at: datetime | None
    deadline: date


@dataclass(frozen=True, slots=True)
class MilestoneProgress:
    project_id: str

    total_weight: Decimal
    completed_weight: Decimal
    remaining_weight: Decimal
    unallocated_weight: Decimal

    progress_percent: Decimal

    total_milestones: int
    completed_milestones: int

    is_plan_complete: bool


class DelayRiskLevel(StrEnum):
    PLAN_INCOMPLETE = "PLAN_INCOMPLETE"
    NOT_STARTED = "NOT_STARTED"
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    OVERDUE = "OVERDUE"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True, slots=True)
class DelayRiskResult:
    project_id: str
    risk_level: DelayRiskLevel

    elapsed_days: int
    total_days: int

    expected_progress_percent: Decimal
    actual_progress_percent: Decimal
    gap_percent: Decimal
