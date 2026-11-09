from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.modules.milestones.domain.entities import (
    DelayRiskLevel,
    DelayRiskResult,
    MilestoneProgress,
    ProjectSchedule,
)


PRECISION = Decimal("0.01")
HUNDRED = Decimal("100.00")
ZERO = Decimal("0.00")

# Heuristik awal: tertinggal >= 10 poin persentase.
RISK_GAP_THRESHOLD = Decimal("10.00")


# ============================================================
# EVALUATE PROJECT DELAY RISK
# ============================================================

def evaluate_delay_risk(
    schedule: ProjectSchedule,
    progress: MilestoneProgress,
    today: date,
) -> DelayRiskResult:
    """
    Estimasi risiko keterlambatan project.

    Membandingkan:
    - Persentase waktu terpakai
    - Persentase bobot milestone selesai

    Menggunakan tanggal yang diberikan,
    bukan mengambil jam sistem secara implisit.
    """

    # ========================================================
    # 1. VERIFY PROJECT
    # ========================================================

    if schedule.project_id != progress.project_id:
        raise ValueError(
            "Data jadwal dan progress berbeda project"
        )

    if not isinstance(today, date):
        raise TypeError(
            "today harus bertipe date"
        )

    # ========================================================
    # 2. PREPARE DURATION
    # ========================================================

    start_date = (
        schedule.started_at.date()
        if schedule.started_at is not None
        else None
    )

    if (
        start_date is not None
        and schedule.deadline < start_date
    ):
        raise ValueError(
            "Deadline tidak boleh lebih awal "
            "dari tanggal mulai project"
        )

    total_days = (
        max(
            1,
            (schedule.deadline - start_date).days,
        )
        if start_date is not None
        else 0
    )

    elapsed_days = (
        max(
            0,
            (today - start_date).days,
        )
        if start_date is not None
        else 0
    )

    # ========================================================
    # 3. CALCULATE EXPECTED PROGRESS
    # ========================================================

    expected = ZERO

    if start_date is not None:

        elapsed_ratio = min(
            Decimal(elapsed_days)
            / Decimal(total_days),
            Decimal("1"),
        )

        expected = (
            elapsed_ratio * HUNDRED
        ).quantize(
            PRECISION,
            rounding=ROUND_HALF_UP,
        )

    actual = progress.progress_percent

    gap = (
        expected - actual
    ).quantize(PRECISION)

    # ========================================================
    # 4. CLASSIFY DELAY RISK
    # ========================================================

    if not progress.is_plan_complete:

        risk = DelayRiskLevel.PLAN_INCOMPLETE

    elif actual >= HUNDRED:

        risk = DelayRiskLevel.COMPLETED

    elif today > schedule.deadline:

        risk = DelayRiskLevel.OVERDUE

    elif (
        start_date is None
        or today < start_date
    ):

        risk = DelayRiskLevel.NOT_STARTED

    elif today == schedule.deadline:

        # Deadline hari ini, tapi belum selesai.
        risk = DelayRiskLevel.AT_RISK

    elif gap >= RISK_GAP_THRESHOLD:

        risk = DelayRiskLevel.AT_RISK

    else:

        risk = DelayRiskLevel.ON_TRACK

    # ========================================================
    # 5. RETURN RISK RESULT
    # ========================================================

    return DelayRiskResult(
        project_id=schedule.project_id,
        risk_level=risk,
        elapsed_days=elapsed_days,
        total_days=total_days,
        expected_progress_percent=expected,
        actual_progress_percent=actual,
        gap_percent=gap,
    )
