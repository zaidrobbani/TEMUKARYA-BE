
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.modules.milestones.domain.entities import (
    DelayRiskLevel,
    MilestoneProgress,
    ProjectSchedule,
)

from app.modules.milestones.domain.delay_risk import (
    evaluate_delay_risk,
)


def make_progress(
    percent: str,
    plan_complete: bool = True,
):
    completed = Decimal(percent)

    return MilestoneProgress(
        project_id="p1",
        total_weight=(
            Decimal("100")
            if plan_complete
            else Decimal("70")
        ),
        completed_weight=completed,
        remaining_weight=(
            (
                Decimal("100")
                if plan_complete
                else Decimal("70")
            ) - completed
        ),
        unallocated_weight=(
            Decimal("0")
            if plan_complete
            else Decimal("30")
        ),
        progress_percent=completed,
        total_milestones=4,
        completed_milestones=2,
        is_plan_complete=plan_complete,
    )


def make_schedule(
    start=datetime(2026, 11, 1),
    deadline=date(2026, 11, 11),
):
    return ProjectSchedule(
        project_id="p1",
        started_at=start,
        deadline=deadline,
    )


def test_project_on_track():
    result = evaluate_delay_risk(
        make_schedule(),
        make_progress("60"),
        date(2026, 11, 6),
    )

    assert result.risk_level == (
        DelayRiskLevel.ON_TRACK
    )

    assert result.expected_progress_percent == (
        Decimal("50.00")
    )


def test_project_at_risk():
    result = evaluate_delay_risk(
        make_schedule(),
        make_progress("30"),
        date(2026, 11, 8),
    )

    assert result.risk_level == (
        DelayRiskLevel.AT_RISK
    )

    assert result.expected_progress_percent == (
        Decimal("70.00")
    )

    assert result.gap_percent == Decimal("40.00")


def test_project_overdue():
    result = evaluate_delay_risk(
        make_schedule(),
        make_progress("90"),
        date(2026, 11, 12),
    )

    assert result.risk_level == (
        DelayRiskLevel.OVERDUE
    )


def test_project_completed():
    result = evaluate_delay_risk(
        make_schedule(),
        make_progress("100"),
        date(2026, 11, 12),
    )

    assert result.risk_level == (
        DelayRiskLevel.COMPLETED
    )


def test_project_not_started():
    result = evaluate_delay_risk(
        make_schedule(start=None),
        make_progress("0"),
        date(2026, 11, 2),
    )

    assert result.risk_level == (
        DelayRiskLevel.NOT_STARTED
    )


def test_plan_incomplete():
    result = evaluate_delay_risk(
        make_schedule(),
        make_progress(
            "30",
            plan_complete=False,
        ),
        date(2026, 11, 6),
    )

    assert result.risk_level == (
        DelayRiskLevel.PLAN_INCOMPLETE
    )


def test_deadline_today_and_unfinished():
    result = evaluate_delay_risk(
        make_schedule(),
        make_progress("80"),
        date(2026, 11, 11),
    )

    assert result.risk_level == (
        DelayRiskLevel.AT_RISK
    )


def test_invalid_deadline():
    schedule = make_schedule(
        start=datetime(2026, 11, 10),
        deadline=date(2026, 11, 1),
    )

    with pytest.raises(ValueError):
        evaluate_delay_risk(
            schedule,
            make_progress("0"),
            date(2026, 11, 5),
        )


def test_wrong_project_rejected():
    schedule = ProjectSchedule(
        project_id="other",
        started_at=datetime(2026, 11, 1),
        deadline=date(2026, 11, 11),
    )

    with pytest.raises(ValueError):
        evaluate_delay_risk(
            schedule,
            make_progress("30"),
            date(2026, 11, 5),
        )