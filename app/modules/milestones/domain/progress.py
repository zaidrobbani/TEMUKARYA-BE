
from collections.abc import Iterable
from decimal import Decimal

from app.modules.milestones.domain.entities import (
    Milestone,
    MilestoneProgress,
    MilestoneStatus,
)

from app.modules.milestones.domain.weight import (
    HUNDRED,
    ZERO,
    validate_milestone_plan,
    validate_weight,
)


# ============================================================
# CALCULATE WEIGHTED PROJECT PROGRESS
# ============================================================

def calculate_milestone_progress(
    project_id: str,
    milestones: Iterable[Milestone],
) -> MilestoneProgress:
    """
    Menghitung progres berdasarkan bobot milestone
    yang berstatus SELESAI.

    Contoh:
    - Milestone A: 20% SELESAI
    - Milestone B: 30% SELESAI
    - Milestone C: 50% BELUM_SELESAI

    Hasil progress = 50%.
    """

    items = tuple(milestones)

    # ========================================================
    # 1. VERIFY PROJECT ID
    # ========================================================

    if not isinstance(project_id, str):
        raise ValueError(
            "Project ID tidak valid"
        )

    project_id = project_id.strip()

    if not project_id:
        raise ValueError(
            "Project ID tidak boleh kosong"
        )

    for item in items:
        if item.project_id != project_id:
            raise ValueError(
                "Milestone bukan milik project ini"
            )

    # ========================================================
    # 2. VALIDATE MILESTONE PLAN
    # ========================================================

    total_weight = validate_milestone_plan(
        items
    )

    # ========================================================
    # 3. COUNT COMPLETED MILESTONES
    # ========================================================

    completed_weight = ZERO
    completed_count = 0

    for item in items:

        if item.status not in (
            MilestoneStatus.BELUM_SELESAI,
            MilestoneStatus.SELESAI,
        ):
            raise ValueError(
                "Status milestone tidak dikenal"
            )

        if item.status == MilestoneStatus.SELESAI:

            completed_weight += validate_weight(
                item.weight_percent
            )

            completed_count += 1

    # ========================================================
    # 4. CALCULATE REMAINING WEIGHT
    # ========================================================

    remaining_weight = (
        total_weight - completed_weight
    )

    unallocated_weight = (
        HUNDRED - total_weight
    )

    # Karena bobot milestone menggunakan
    # skala dari total project 100%,
    # progress sama dengan bobot yang selesai.
    progress_percent = completed_weight

    # ========================================================
    # 5. RETURN PROGRESS
    # ========================================================

    return MilestoneProgress(
        project_id=project_id,
        total_weight=total_weight,
        completed_weight=completed_weight,
        remaining_weight=remaining_weight,
        unallocated_weight=unallocated_weight,
        progress_percent=progress_percent,
        total_milestones=len(items),
        completed_milestones=completed_count,
        is_plan_complete=(
            total_weight == HUNDRED
        ),
    )