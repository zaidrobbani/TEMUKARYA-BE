from dataclasses import FrozenInstanceError
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.modules.milestones.domain.entities import (
    DelayRiskLevel,
    Milestone,
    MilestoneStatus,
    ProjectSchedule,
)


def test_milestone_status_values():
    assert MilestoneStatus.BELUM_SELESAI.value == (
        "BELUM_SELESAI"
    )
    assert MilestoneStatus.SELESAI.value == "SELESAI"


def test_milestone_entity():
    milestone = Milestone(
        id="m1",
        project_id="p1",
        name="Frontend",
        description="Membuat halaman website",
        weight_percent=Decimal("30.00"),
        status=MilestoneStatus.BELUM_SELESAI,
        sort_order=1,
    )

    assert milestone.project_id == "p1"
    assert milestone.weight_percent == Decimal("30.00")
    assert milestone.completed_at is None


def test_milestone_is_immutable():
    milestone = Milestone(
        id="m1",
        project_id="p1",
        name="Frontend",
        description="Frontend",
        weight_percent=Decimal("30.00"),
        status=MilestoneStatus.BELUM_SELESAI,
        sort_order=1,
    )

    with pytest.raises(FrozenInstanceError):
        milestone.name = "Changed"


def test_project_schedule_entity():
    schedule = ProjectSchedule(
        project_id="p1",
        started_at=datetime(2026, 11, 1),
        deadline=date(2026, 11, 11),
    )

    assert schedule.deadline == date(2026, 11, 11)


def test_delay_risk_levels():
    assert DelayRiskLevel.AT_RISK == "AT_RISK"
    assert DelayRiskLevel.OVERDUE == "OVERDUE"
    assert DelayRiskLevel.PLAN_INCOMPLETE == (
        "PLAN_INCOMPLETE"
    )