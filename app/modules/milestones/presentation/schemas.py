from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.responses import UtcDateTime

from app.modules.milestones.domain.entities import (
    DelayRiskLevel,
    MilestoneStatus,
)


# ============================================================
# BASE RESPONSE CONFIGURATION
# ============================================================

class MilestoneBaseResponse(BaseModel):
    """
    Memungkinkan Pydantic membaca atribut
    langsung dari dataclass Domain Layer.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )


# ============================================================
# 1. MILESTONE DETAIL RESPONSE
# ============================================================

class MilestoneResponse(MilestoneBaseResponse):

    id: str
    project_id: str
    name: str
    description: str

    weight_percent: Decimal = Field(
        ge=Decimal("0"),
        le=Decimal("100"),
    )

    status: MilestoneStatus
    sort_order: int

    completed_at: UtcDateTime | None = None
    updated_by_user_id: str | None = None


# ============================================================
# 2. MILESTONE PLAN RESPONSE
# ============================================================

class MilestonePlanResponse(MilestoneBaseResponse):

    project_id: str
    items: list[MilestoneResponse]

    total_weight: Decimal
    is_plan_complete: bool


# ============================================================
# 3. WEIGHTED PROGRESS RESPONSE
# ============================================================

class MilestoneProgressResponse(MilestoneBaseResponse):

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
# 4. DELAY RISK RESPONSE
# ============================================================

class MilestoneDelayRiskResponse(MilestoneBaseResponse):

    project_id: str
    risk_level: DelayRiskLevel

    elapsed_days: int
    total_days: int

    expected_progress_percent: Decimal
    actual_progress_percent: Decimal
    gap_percent: Decimal