from decimal import Decimal

import pytest

from app.modules.milestones.domain.entities import (
    Milestone,
    MilestoneStatus,
)

from app.modules.milestones.domain.progress import (
    calculate_milestone_progress,
)


def make_milestone(
    number: int,
    weight: str,
    completed: bool = False,
):
    return Milestone(
        id=f"m{number}",
        project_id="p1",
        name=f"Milestone {number}",
        description="Test milestone",
        weight_percent=Decimal(weight),
        status=(
            MilestoneStatus.SELESAI
            if completed
            else MilestoneStatus.BELUM_SELESAI
        ),
        sort_order=number,
    )


def test_weighted_progress_50_percent():
    milestones = [
        make_milestone(1, "20", True),
        make_milestone(2, "30", True),
        make_milestone(3, "50", False),
    ]

    result = calculate_milestone_progress(
        "p1",
        milestones,
    )

    assert result.progress_percent == Decimal("50")
    assert result.completed_weight == Decimal("50")
    assert result.remaining_weight == Decimal("50")
    assert result.is_plan_complete is True


def test_progress_not_based_on_milestone_count():
    milestones = [
        make_milestone(1, "10", True),
        make_milestone(2, "90", False),
    ]

    result = calculate_milestone_progress(
        "p1",
        milestones,
    )

    assert result.completed_milestones == 1
    assert result.total_milestones == 2
    assert result.progress_percent == Decimal("10")


def test_all_milestones_completed():
    milestones = [
        make_milestone(1, "40", True),
        make_milestone(2, "60", True),
    ]

    result = calculate_milestone_progress(
        "p1",
        milestones,
    )

    assert result.progress_percent == Decimal("100")
    assert result.remaining_weight == Decimal("0")
    assert result.is_plan_complete is True


def test_no_milestones():
    result = calculate_milestone_progress(
        "p1",
        [],
    )

    assert result.total_milestones == 0
    assert result.progress_percent == Decimal("0")
    assert result.is_plan_complete is False


def test_draft_plan_has_unallocated_weight():
    milestones = [
        make_milestone(1, "30", True),
    ]

    result = calculate_milestone_progress(
        "p1",
        milestones,
    )

    assert result.total_weight == Decimal("30")
    assert result.completed_weight == Decimal("30")
    assert result.unallocated_weight == Decimal("70")
    assert result.is_plan_complete is False


def test_wrong_project_rejected():
    milestones = [
        make_milestone(1, "100", True),
    ]

    with pytest.raises(ValueError):
        calculate_milestone_progress(
            "other-project",
            milestones,
        )


def test_duplicate_order_rejected():
    milestones = [
        make_milestone(1, "50"),
        make_milestone(1, "50"),
    ]

    with pytest.raises(ValueError):
        calculate_milestone_progress(
            "p1",
            milestones,
        )