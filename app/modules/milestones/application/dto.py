
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.modules.milestones.domain.entities import (
    Milestone,
)


# ============================================================
# 1. AUTHENTICATED ACTOR
# ============================================================

@dataclass(frozen=True, slots=True)
class MilestoneActor:
    """
    Identitas pengguna dari sistem autentikasi.

    Jangan mengambil user_id atau role dari
    query parameter yang dikirim pengguna.
    """

    user_id: str
    role: str


# ============================================================
# 2. MILESTONE DRAFT INPUT
# ============================================================

@dataclass(frozen=True, slots=True)
class MilestoneDraft:
    name: str
    description: str
    weight_percent: Decimal
    sort_order: int


# ============================================================
# 3. GET MILESTONE PLAN INPUT
# ============================================================

@dataclass(frozen=True, slots=True)
class GetMilestonePlanInput:
    project_id: str
    actor: MilestoneActor


# ============================================================
# 4. REPLACE MILESTONE PLAN INPUT
# ============================================================

@dataclass(frozen=True, slots=True)
class ReplaceMilestonePlanInput:
    project_id: str
    actor: MilestoneActor
    items: tuple[MilestoneDraft, ...]


# ============================================================
# 5. COMPLETE MILESTONE INPUT
# ============================================================

@dataclass(frozen=True, slots=True)
class CompleteMilestoneInput:
    project_id: str
    milestone_id: str
    actor: MilestoneActor


# ============================================================
# 6. GET DELAY RISK INPUT
# ============================================================

@dataclass(frozen=True, slots=True)
class GetDelayRiskInput:
    project_id: str
    actor: MilestoneActor
    today: date


# ============================================================
# 7. MILESTONE PLAN RESULT
# ============================================================

@dataclass(frozen=True, slots=True)
class MilestonePlanResult:
    project_id: str
    items: tuple[Milestone, ...]
    total_weight: Decimal
    is_plan_complete: bool