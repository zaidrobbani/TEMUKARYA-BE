from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.modules.milestones.application.dto import (
    CompleteMilestoneInput,
    MilestoneActor,
    MilestoneDraft,
    ReplaceMilestonePlanInput,
)
from app.modules.milestones.domain.entities import Milestone, MilestoneStatus
from app.modules.milestones.domain.repositories import ProjectMilestoneContext
from app.modules.notifications.application.use_cases import Notifier
from app.modules.workflow.application.milestone_actions import MarkMilestoneDone, SaveMilestonePlan
from tests.fakes import FakeUnitOfWork
from tests.modules.workflow.fakes import Clock, FakeNotificationRepository, Store

UMKM = MilestoneActor("umkm-1", "UMKM")
FREELANCER = MilestoneActor("freelancer-1", "FREELANCER")
OTHER = MilestoneActor("freelancer-2", "FREELANCER")


class FakeRepo:
    def __init__(self, status="MENUNGGU_KESEPAKATAN"):
        self.context = ProjectMilestoneContext("p1", "umkm-1", status, None, date(2026, 12, 1), "freelancer-1")
        self.items: list[Milestone] = []
        self.resets = 0

    def get_project_context(self, project_id):
        return self.context if project_id == "p1" else None

    def list_milestones(self, project_id):
        return tuple(self.items)

    def get_total_weight(self, project_id):
        return sum((m.weight_percent for m in self.items), Decimal("0"))

    def replace_plan_and_reset_approvals(self, project_id, milestones):
        self.resets += 1
        self.items = list(milestones)

    def complete_if_pending(self, project_id, milestone_id, updated_by_user_id, completed_at):
        for i, m in enumerate(self.items):
            if m.id == milestone_id and m.status == MilestoneStatus.BELUM_SELESAI:
                self.items[i] = replace(m, status=MilestoneStatus.SELESAI, completed_at=completed_at)
                return True
        return False


@pytest.fixture
def ctx():
    store = Store()
    return FakeRepo(), Notifier(FakeNotificationRepository(store), Clock()), FakeUnitOfWork(), store


def plan(actor, weights=("20", "30", "35", "15")):
    return ReplaceMilestonePlanInput(
        "p1",
        actor,
        tuple(
            MilestoneDraft(f"Tahap {i}", "", Decimal(w), i) for i, w in enumerate(weights, start=1)
        ),
    )


def test_freelancer_proposes_plan_and_umkm_notified(ctx):
    repo, notifier, uow, store = ctx
    result = SaveMilestonePlan(repo, notifier, uow).execute(plan(FREELANCER))
    assert result.is_plan_complete is True
    assert repo.resets == 1
    assert uow.commits == 1
    assert store.notifications[-1].user_id == "umkm-1"
    assert "100%" in store.notifications[-1].body


def test_umkm_edits_draft_plan_and_freelancer_notified(ctx):
    repo, notifier, uow, store = ctx
    result = SaveMilestonePlan(repo, notifier, uow).execute(plan(UMKM, ("50",)))
    assert result.is_plan_complete is False
    assert store.notifications[-1].user_id == "freelancer-1"


def test_plan_locked_after_final(ctx):
    repo, notifier, uow, _ = ctx
    repo.context = replace(repo.context, status="MENUNGGU_PEMBAYARAN")
    with pytest.raises(ConflictError, match="sebelum kesepakatan final"):
        SaveMilestonePlan(repo, notifier, uow).execute(plan(FREELANCER))
    assert uow.commits == 0


def test_plan_over_100_rejected(ctx):
    repo, notifier, uow, _ = ctx
    with pytest.raises(BadRequestError):
        SaveMilestonePlan(repo, notifier, uow).execute(plan(FREELANCER, ("60", "50")))


def test_plan_outsider_rejected(ctx):
    repo, notifier, uow, _ = ctx
    with pytest.raises(NotFoundError):
        SaveMilestonePlan(repo, notifier, uow).execute(plan(OTHER))


def test_complete_notifies_once(ctx):
    repo, notifier, uow, store = ctx
    SaveMilestonePlan(repo, notifier, uow).execute(plan(FREELANCER))
    repo.context = replace(repo.context, status="SEDANG_DIKERJAKAN")
    target = repo.items[0].id
    before = len(store.notifications)

    progress = MarkMilestoneDone(repo, notifier, uow).execute(CompleteMilestoneInput("p1", target, FREELANCER))
    MarkMilestoneDone(repo, notifier, uow).execute(CompleteMilestoneInput("p1", target, FREELANCER))

    assert progress.progress_percent == Decimal("20")
    assert len(store.notifications) == before + 1
    assert store.notifications[-1].notification_type == "MILESTONE_COMPLETED"
    assert "progres kini 20%" in store.notifications[-1].body


@pytest.mark.parametrize(
    "status, message",
    [
        ("SIAP_DIKERJAKAN", "Mulai Pengerjaan"),
        ("MENUNGGU_REVIEW", "direview"),
        ("SELESAI", "sudah selesai"),
        ("MENUNGGU_KESEPAKATAN", "saat proyek dikerjakan"),
    ],
)
def test_complete_wrong_status(ctx, status, message):
    repo, notifier, uow, _ = ctx
    SaveMilestonePlan(repo, notifier, uow).execute(plan(FREELANCER))
    repo.context = replace(repo.context, status=status)
    with pytest.raises(ConflictError, match=message):
        MarkMilestoneDone(repo, notifier, uow).execute(CompleteMilestoneInput("p1", repo.items[0].id, FREELANCER))


def test_complete_allowed_during_revision(ctx):
    repo, notifier, uow, _ = ctx
    SaveMilestonePlan(repo, notifier, uow).execute(plan(FREELANCER))
    repo.context = replace(repo.context, status="REVISI")
    progress = MarkMilestoneDone(repo, notifier, uow).execute(CompleteMilestoneInput("p1", repo.items[1].id, FREELANCER))
    assert progress.completed_milestones == 1


def test_umkm_cannot_complete(ctx):
    repo, notifier, uow, _ = ctx
    SaveMilestonePlan(repo, notifier, uow).execute(plan(FREELANCER))
    repo.context = replace(repo.context, status="SEDANG_DIKERJAKAN")
    with pytest.raises(ForbiddenError):
        MarkMilestoneDone(repo, notifier, uow).execute(CompleteMilestoneInput("p1", repo.items[0].id, UMKM))
