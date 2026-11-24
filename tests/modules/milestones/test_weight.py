from decimal import Decimal

import pytest

from app.modules.milestones.domain.entities import (
    Milestone,
    MilestoneStatus,
)

from app.modules.milestones.domain.weight import (
    calculate_total_weight,
    require_complete_plan,
    validate_milestone_plan,
    validate_weight,
)


def make_milestone(
    number: int,
    weight: str,
    project_id: str = "p1",
    sort_order: int | None = None,
):
    return Milestone(
        id=f"m{number}",
        project_id=project_id,
        name=f"Milestone {number}",
        description="Test",
        weight_percent=Decimal(weight),
        status=MilestoneStatus.BELUM_SELESAI,
        sort_order=(
            sort_order
            if sort_order is not None
            else number
        ),
    )


def test_valid_weight():
    assert validate_weight(
        Decimal("30.00")
    ) == Decimal("30.00")


@pytest.mark.parametrize(
    "weight",
    [
        Decimal("0"),
        Decimal("-5"),
        Decimal("100.01"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("10.555"),
    ],
)
def test_invalid_weight(weight):
    with pytest.raises(ValueError):
        validate_weight(weight)


def test_float_weight_rejected():
    with pytest.raises(TypeError):
        validate_weight(33.33)


def test_exact_total_100():
    milestones = [
        make_milestone(1, "33.33"),
        make_milestone(2, "33.33"),
        make_milestone(3, "33.34"),
    ]

    assert calculate_total_weight(
        milestones
    ) == Decimal("100.00")

    assert require_complete_plan(
        milestones
    ) == Decimal("100.00")


def test_partial_plan_allowed_as_draft():
    milestones = [
        make_milestone(1, "20.00"),
        make_milestone(2, "30.00"),
    ]

    assert validate_milestone_plan(
        milestones
    ) == Decimal("50.00")

    with pytest.raises(ValueError):
        require_complete_plan(milestones)


def test_total_over_100_rejected():
    milestones = [
        make_milestone(1, "60"),
        make_milestone(2, "50"),
    ]

    with pytest.raises(ValueError):
        validate_milestone_plan(milestones)


def test_duplicate_sort_order_rejected():
    milestones = [
        make_milestone(1, "50", sort_order=1),
        make_milestone(2, "50", sort_order=1),
    ]

    with pytest.raises(ValueError):
        validate_milestone_plan(milestones)


def test_mixed_project_ids_rejected():
    milestones = [
        make_milestone(1, "50", project_id="p1"),
        make_milestone(2, "50", project_id="p2"),
    ]

    with pytest.raises(ValueError):
        validate_milestone_plan(milestones)


def test_empty_plan_total_zero():
    assert calculate_total_weight(
        []
    ) == Decimal("0.00")

    with pytest.raises(ValueError):
        require_complete_plan([])