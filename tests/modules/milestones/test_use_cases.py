
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

from app.modules.milestones.application.dto import (
    CompleteMilestoneInput,
    GetDelayRiskInput,
    GetMilestonePlanInput,
    MilestoneActor,
    MilestoneDraft,
    ReplaceMilestonePlanInput,
)

from app.modules.milestones.application.use_cases import (
    CompleteMilestone,
    GetMilestonePlan,
    GetMilestoneProgress,
    GetProjectDelayRisk,
    GetTotalMilestoneWeight,
    ReplaceMilestonePlan,
)

from app.modules.milestones.domain.entities import (
    DelayRiskLevel,
    Milestone,
    MilestoneStatus,
)

from app.modules.milestones.domain.repositories import (
    ProjectMilestoneContext,
)


# ============================================================
# TEST CONSTANTS
# ============================================================

PROJECT_ID = "project-1"

UMKM = MilestoneActor(
    user_id="umkm-1",
    role="UMKM",
)

FREELANCER = MilestoneActor(
    user_id="freelancer-1",
    role="FREELANCER",
)

OUTSIDER = MilestoneActor(
    user_id="another-umkm",
    role="UMKM",
)


# ============================================================
# TEST DATA FACTORY
# ============================================================

def make_milestone(
    milestone_id: str,
    weight: str,
    order: int,
    completed: bool = False,
) -> Milestone:

    return Milestone(
        id=milestone_id,
        project_id=PROJECT_ID,
        name=f"Milestone {order}",
        description="Test milestone",
        weight_percent=Decimal(weight),
        status=(
            MilestoneStatus.SELESAI
            if completed
            else MilestoneStatus.BELUM_SELESAI
        ),
        sort_order=order,
        completed_at=(
            datetime(2026, 11, 3)
            if completed
            else None
        ),
    )


# ============================================================
# FAKE REPOSITORY
# ============================================================

class FakeMilestoneRepository:

    def __init__(self):

        self.project = ProjectMilestoneContext(
            project_id=PROJECT_ID,
            umkm_id=UMKM.user_id,
            freelancer_id=FREELANCER.user_id,
            status="SEDANG_DIKERJAKAN",
            started_at=datetime(2026, 11, 1),
            deadline=date(2026, 11, 11),
        )

        self.milestones = [
            make_milestone("m1", "20", 1, True),
            make_milestone("m2", "30", 2, True),
            make_milestone("m3", "50", 3, False),
        ]

        self.replace_calls = 0
        self.reset_approvals_calls = 0
        self.complete_calls = 0

        self.force_completion_conflict = False

    def get_project_context(
        self,
        project_id,
    ):
        if (
            self.project is not None
            and project_id == self.project.project_id
        ):
            return self.project

        return None

    def list_milestones(
        self,
        project_id,
    ):
        if project_id != PROJECT_ID:
            return ()

        return tuple(self.milestones)

    def get_total_weight(
        self,
        project_id,
    ):
        if project_id != PROJECT_ID:
            return Decimal("0.00")

        return sum(
            (
                item.weight_percent
                for item in self.milestones
            ),
            Decimal("0.00"),
        )

    def replace_plan_and_reset_approvals(
        self,
        project_id,
        milestones,
    ):
        assert project_id == PROJECT_ID

        self.replace_calls += 1
        self.reset_approvals_calls += 1

        self.milestones = list(milestones)

    def complete_if_pending(
        self,
        project_id,
        milestone_id,
        updated_by_user_id,
        completed_at,
    ):
        self.complete_calls += 1

        if self.force_completion_conflict:
            return False

        for index, item in enumerate(self.milestones):

            if (
                item.project_id == project_id
                and item.id == milestone_id
                and item.status
                == MilestoneStatus.BELUM_SELESAI
            ):
                self.milestones[index] = replace(
                    item,
                    status=MilestoneStatus.SELESAI,
                    completed_at=completed_at,
                    updated_by_user_id=(
                        updated_by_user_id
                    ),
                )

                return True

        return False


# ============================================================
# FAKE WORKFLOW POLICY
# ============================================================

class FakeWorkflowPolicy:
    """
    Policy untuk test saja.

    Production harus menggunakan aturan
    Workflow resmi milik Zaid.
    """

    def __init__(
        self,
        allow_plan=True,
        allow_completion=True,
    ):
        self.allow_plan = allow_plan
        self.allow_completion = allow_completion

    def require_plan_editable(
        self,
        project,
        actor,
    ):
        if not self.allow_plan:
            raise ConflictError(
                "Rencana tidak boleh diubah"
            )

    def require_completion_allowed(
        self,
        project,
        actor,
    ):
        if not self.allow_completion:
            raise ConflictError(
                "Milestone belum boleh selesai"
            )


# ============================================================
# TEST FIXTURE
# ============================================================

@pytest.fixture
def context():

    repository = FakeMilestoneRepository()
    policy = FakeWorkflowPolicy()

    return repository, policy


# ============================================================
# 1. READ PLAN
# ============================================================

def test_umkm_can_read_own_plan(context):
    repo, _ = context

    result = GetMilestonePlan(repo).execute(
        GetMilestonePlanInput(
            project_id=PROJECT_ID,
            actor=UMKM,
        )
    )

    assert result.total_weight == Decimal("100")
    assert result.is_plan_complete is True
    assert len(result.items) == 3


def test_assigned_freelancer_can_read_plan(context):
    repo, _ = context

    result = GetMilestonePlan(repo).execute(
        GetMilestonePlanInput(
            project_id=PROJECT_ID,
            actor=FREELANCER,
        )
    )

    assert len(result.items) == 3


def test_other_umkm_cannot_read_plan(context):
    repo, _ = context

    with pytest.raises(NotFoundError):
        GetMilestonePlan(repo).execute(
            GetMilestonePlanInput(
                PROJECT_ID,
                OUTSIDER,
            )
        )


def test_unassigned_freelancer_cannot_read_plan(
    context,
):
    repo, _ = context

    actor = MilestoneActor(
        "another-freelancer",
        "FREELANCER",
    )

    with pytest.raises(NotFoundError):
        GetMilestonePlan(repo).execute(
            GetMilestonePlanInput(
                PROJECT_ID,
                actor,
            )
        )


def test_missing_project_returns_404(context):
    repo, _ = context

    with pytest.raises(NotFoundError):
        GetMilestonePlan(repo).execute(
            GetMilestonePlanInput(
                "missing",
                UMKM,
            )
        )


def test_empty_plan_is_valid_draft(context):
    repo, _ = context

    repo.milestones = []

    result = GetMilestonePlan(repo).execute(
        GetMilestonePlanInput(
            PROJECT_ID,
            UMKM,
        )
    )

    assert result.items == ()
    assert result.total_weight == Decimal("0")
    assert not result.is_plan_complete


def test_invalid_project_id_rejected(context):
    repo, _ = context

    with pytest.raises(BadRequestError):
        GetMilestonePlan(repo).execute(
            GetMilestonePlanInput(
                "",
                UMKM,
            )
        )


def test_invalid_role_rejected(context):
    repo, _ = context

    actor = MilestoneActor(
        "admin-1",
        "ADMIN",
    )

    with pytest.raises(ForbiddenError):
        GetMilestonePlan(repo).execute(
            GetMilestonePlanInput(
                PROJECT_ID,
                actor,
            )
        )


def test_corrupted_plan_rejected(context):
    repo, _ = context

    repo.milestones.append(
        make_milestone(
            "m4",
            "90",
            4,
        )
    )

    with pytest.raises(ConflictError):
        GetMilestonePlan(repo).execute(
            GetMilestonePlanInput(
                PROJECT_ID,
                UMKM,
            )
        )


# ============================================================
# 2. TOTAL WEIGHT FOR WORKFLOW
# ============================================================

def test_workflow_get_total_weight(context):
    repo, _ = context

    result = GetTotalMilestoneWeight(
        repo
    ).execute(PROJECT_ID)

    assert result == Decimal("100")


def test_workflow_total_weight_empty_plan(context):
    repo, _ = context

    repo.milestones = []

    result = GetTotalMilestoneWeight(
        repo
    ).execute(PROJECT_ID)

    assert result == Decimal("0")


def test_workflow_total_weight_missing_project(
    context,
):
    repo, _ = context

    with pytest.raises(NotFoundError):
        GetTotalMilestoneWeight(
            repo
        ).execute("missing")


# ============================================================
# 3. WEIGHTED PROGRESS
# ============================================================

def test_weighted_progress_is_50_percent(context):
    repo, _ = context

    result = GetMilestoneProgress(repo).execute(
        GetMilestonePlanInput(
            PROJECT_ID,
            UMKM,
        )
    )

    assert result.progress_percent == Decimal("50")
    assert result.completed_weight == Decimal("50")
    assert result.remaining_weight == Decimal("50")
    assert result.total_milestones == 3
    assert result.completed_milestones == 2


def test_progress_not_accessible_by_outsider(context):
    repo, _ = context

    with pytest.raises(NotFoundError):
        GetMilestoneProgress(repo).execute(
            GetMilestonePlanInput(
                PROJECT_ID,
                OUTSIDER,
            )
        )


# ============================================================
# 4. DELAY RISK
# ============================================================

def test_delay_risk_at_risk(context):
    repo, _ = context

    result = GetProjectDelayRisk(repo).execute(
        GetDelayRiskInput(
            project_id=PROJECT_ID,
            actor=UMKM,
            today=date(2026, 11, 8),
        )
    )

    assert result.risk_level == (
        DelayRiskLevel.AT_RISK
    )

    assert result.expected_progress_percent == (
        Decimal("70.00")
    )

    assert result.actual_progress_percent == (
        Decimal("50.00")
    )


def test_delay_risk_rejects_outsider(context):
    repo, _ = context

    with pytest.raises(NotFoundError):
        GetProjectDelayRisk(repo).execute(
            GetDelayRiskInput(
                PROJECT_ID,
                OUTSIDER,
                date(2026, 11, 8),
            )
        )


# ============================================================
# 5. REPLACE MILESTONE PLAN
# ============================================================

def make_plan_input(
    actor=UMKM,
    weights=("40.00", "60.00"),
):
    return ReplaceMilestonePlanInput(
        project_id=PROJECT_ID,
        actor=actor,
        items=tuple(
            MilestoneDraft(
                name=f"New milestone {index}",
                description="Updated plan",
                weight_percent=Decimal(weight),
                sort_order=index,
            )
            for index, weight in enumerate(
                weights,
                start=1,
            )
        ),
    )


def test_replace_plan_when_workflow_allows(context):
    repo, policy = context

    result = ReplaceMilestonePlan(
        repo,
        policy,
    ).execute(
        make_plan_input()
    )

    assert result.total_weight == Decimal("100")
    assert result.is_plan_complete is True

    assert len(repo.milestones) == 2
    assert repo.replace_calls == 1
    assert repo.reset_approvals_calls == 1

    assert all(
        item.status == MilestoneStatus.BELUM_SELESAI
        for item in repo.milestones
    )


def test_replace_plan_draft_allowed(context):
    repo, policy = context

    result = ReplaceMilestonePlan(
        repo,
        policy,
    ).execute(
        make_plan_input(weights=("40.00",))
    )

    assert result.total_weight == Decimal("40")
    assert not result.is_plan_complete


def test_replace_plan_over_100_rejected(context):
    repo, policy = context

    with pytest.raises(BadRequestError):
        ReplaceMilestonePlan(
            repo,
            policy,
        ).execute(
            make_plan_input(
                weights=("80", "40")
            )
        )

    assert repo.replace_calls == 0


def test_replace_plan_duplicate_order_rejected(
    context,
):
    repo, policy = context

    data = ReplaceMilestonePlanInput(
        project_id=PROJECT_ID,
        actor=UMKM,
        items=(
            MilestoneDraft(
                "First",
                "Test",
                Decimal("50"),
                1,
            ),
            MilestoneDraft(
                "Second",
                "Test",
                Decimal("50"),
                1,
            ),
        ),
    )

    with pytest.raises(BadRequestError):
        ReplaceMilestonePlan(
            repo,
            policy,
        ).execute(data)

    assert repo.replace_calls == 0


def test_replace_plan_selected_freelancer_can_edit(
    context,
):
    repo, policy = context

    result = ReplaceMilestonePlan(
        repo,
        policy,
    ).execute(
        make_plan_input(
            actor=FREELANCER
        )
    )

    assert result.is_plan_complete is True
    assert repo.replace_calls == 1


def test_replace_plan_outsider_cannot_edit(
    context,
):
    repo, policy = context

    with pytest.raises(NotFoundError):
        ReplaceMilestonePlan(
            repo,
            policy,
        ).execute(
            make_plan_input(
                actor=OUTSIDER
            )
        )

    assert repo.replace_calls == 0


def test_replace_plan_outsider_denied(context):
    repo, policy = context

    with pytest.raises(NotFoundError):
        ReplaceMilestonePlan(
            repo,
            policy,
        ).execute(
            make_plan_input(
                actor=OUTSIDER
            )
        )

    assert repo.replace_calls == 0


def test_replace_plan_fails_closed_by_default(
    context,
):
    repo, _ = context

    with pytest.raises(ConflictError):
        ReplaceMilestonePlan(
            repo
        ).execute(
            make_plan_input()
        )

    assert repo.replace_calls == 0


def test_replace_plan_workflow_denies(context):
    repo, _ = context

    policy = FakeWorkflowPolicy(
        allow_plan=False,
    )

    with pytest.raises(ConflictError):
        ReplaceMilestonePlan(
            repo,
            policy,
        ).execute(
            make_plan_input()
        )

    assert repo.replace_calls == 0


# ============================================================
# 6. COMPLETE MILESTONE
# ============================================================

def completion_input(
    milestone_id="m3",
    actor=FREELANCER,
):
    return CompleteMilestoneInput(
        project_id=PROJECT_ID,
        milestone_id=milestone_id,
        actor=actor,
    )


def test_complete_milestone_updates_progress(
    context,
):
    repo, policy = context

    result = CompleteMilestone(
        repo,
        policy,
    ).execute(
        completion_input()
    )

    assert result.progress_percent == Decimal("100")
    assert result.completed_milestones == 3
    assert repo.complete_calls == 1

    target = repo.milestones[2]

    assert target.status == MilestoneStatus.SELESAI
    assert target.completed_at is not None
    assert target.updated_by_user_id == (
        FREELANCER.user_id
    )


def test_double_complete_is_idempotent(context):
    repo, policy = context

    use_case = CompleteMilestone(
        repo,
        policy,
    )

    first = use_case.execute(
        completion_input()
    )

    second = use_case.execute(
        completion_input()
    )

    assert first.progress_percent == Decimal("100")
    assert second.progress_percent == Decimal("100")

    # Hanya satu perubahan database.
    assert repo.complete_calls == 1


def test_complete_unknown_milestone_rejected(
    context,
):
    repo, policy = context

    with pytest.raises(NotFoundError):
        CompleteMilestone(
            repo,
            policy,
        ).execute(
            completion_input("unknown")
        )

    assert repo.complete_calls == 0


def test_complete_outsider_rejected(context):
    repo, policy = context

    with pytest.raises(NotFoundError):
        CompleteMilestone(
            repo,
            policy,
        ).execute(
            completion_input(
                actor=MilestoneActor(
                    "another-user",
                    "FREELANCER",
                )
            )
        )

    assert repo.complete_calls == 0


def test_complete_fails_closed_by_default(
    context,
):
    repo, _ = context

    with pytest.raises(ConflictError):
        CompleteMilestone(
            repo
        ).execute(
            completion_input()
        )

    assert repo.complete_calls == 0


def test_complete_workflow_denies(context):
    repo, _ = context

    policy = FakeWorkflowPolicy(
        allow_completion=False
    )

    with pytest.raises(ConflictError):
        CompleteMilestone(
            repo,
            policy,
        ).execute(
            completion_input()
        )

    assert repo.complete_calls == 0


def test_concurrent_completion_conflict(context):
    repo, policy = context

    repo.force_completion_conflict = True

    with pytest.raises(ConflictError):
        CompleteMilestone(
            repo,
            policy,
        ).execute(
            completion_input()
        )

    assert repo.complete_calls == 1