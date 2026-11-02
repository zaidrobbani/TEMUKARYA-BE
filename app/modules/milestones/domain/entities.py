
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


# ============================================================
# 1. MILESTONE STATUS
# ============================================================

class MilestoneStatus(StrEnum):
    BELUM_SELESAI = "BELUM_SELESAI"
    SELESAI = "SELESAI"


# ============================================================
# 2. PROJECT MILESTONE ENTITY
# ============================================================

@dataclass(frozen=True, slots=True)
class Milestone:
    """
    Representasi satu tahapan pekerjaan project.

    Mengikuti tabel project_milestones.
    """

    id: str
    project_id: str
    name: str
    description: str
    weight_percent: Decimal
    status: MilestoneStatus
    sort_order: int

    completed_at: datetime | None = None
    updated_by_user_id: str | None = None


# ============================================================
# 3. PROJECT SCHEDULE
# ============================================================

@dataclass(frozen=True, slots=True)
class ProjectSchedule:
    """
    Data waktu yang dimiliki Projects/Workflow.

    Milestones hanya membaca data ini.
    """

    project_id: str
    started_at: datetime | None
    deadline: date


# ============================================================
# 4. MILESTONE PROGRESS
# ============================================================

@dataclass(frozen=True, slots=True)
class MilestoneProgress:
    """
    Ringkasan progres berbobot project.
    """

    project_id: str

    total_weight: Decimal
    completed_weight: Decimal
    remaining_weight: Decimal
    unallocated_weight: Decimal

    progress_percent: Decimal

    total_milestones: int
    completed_milestones: int

    is_plan_complete: bool


# ============================================================
# 5. DELAY RISK LEVEL
# ============================================================

class DelayRiskLevel(StrEnum):
    PLAN_INCOMPLETE = "PLAN_INCOMPLETE"
    NOT_STARTED = "NOT_STARTED"
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    OVERDUE = "OVERDUE"
    COMPLETED = "COMPLETED"


# ============================================================
# 6. DELAY RISK RESULT
# ============================================================

@dataclass(frozen=True, slots=True)
class DelayRiskResult:
    """
    Hasil estimasi risiko keterlambatan project.
    """

    project_id: str
    risk_level: DelayRiskLevel

    elapsed_days: int
    total_days: int

    expected_progress_percent: Decimal
    actual_progress_percent: Decimal
    gap_percent: Decimal