from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.users.domain.entities import UserRole
from app.modules.workflow.application.dto import Actor, Cancellation, WorkflowDetail
from app.modules.workflow.domain.entities import (
    Agreement,
    AgreementStatus,
    ChangeSource,
    Party,
    ProjectStatus,
    StatusHistoryEntry,
    WorkflowAction,
    WorkflowProject,
    status_label,
)
from app.modules.workflow.domain.repositories import WorkflowRepository
from app.modules.workflow.domain.rules import available_actions, can_transition

Clock = Callable[[], datetime]
PROJECT_NOT_FOUND = "Proyek tidak ditemukan"


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ProjectContext:
    project: WorkflowProject
    agreement: Agreement | None
    party: Party


def resolve_party(project: WorkflowProject, agreement: Agreement | None, actor: Actor) -> Party | None:
    if actor.role == UserRole.UMKM and actor.user_id == project.umkm_id:
        return Party.UMKM
    if actor.role == UserRole.FREELANCER and agreement is not None and agreement.freelancer_id == actor.user_id:
        return Party.FREELANCER
    return None


class ProjectAccess:
    """Memuat project + kesepakatan dan memastikan actor adalah pihak di project itu."""

    def __init__(self, repository: WorkflowRepository):
        self._repository = repository

    def load(self, project_id: str, actor: Actor, lock: bool = False) -> ProjectContext:
        project = self._repository.get_project(project_id, lock=lock)
        if project is None:
            raise NotFoundError(PROJECT_NOT_FOUND)
        agreement = self._repository.get_agreement(project_id, lock=lock)
        party = resolve_party(project, agreement, actor)
        # 404 (bukan 403) supaya keberadaan project milik orang lain tidak bocor.
        if party is None:
            raise NotFoundError(PROJECT_NOT_FOUND)
        return ProjectContext(project, agreement, party)


def change_status(
    repository: WorkflowRepository,
    project: WorkflowProject,
    new_status: ProjectStatus,
    action: WorkflowAction,
    actor_id: str | None,
    now: datetime,
    source: ChangeSource = ChangeSource.USER,
    reason: str | None = None,
    reason_code: str | None = None,
) -> WorkflowProject:
    if not can_transition(project.status, new_status):
        raise ConflictError(
            f"Status proyek tidak dapat berubah dari {status_label(project.status)} "
            f"ke {status_label(new_status)}"
        )
    started_at = now if new_status == ProjectStatus.SEDANG_DIKERJAKAN else None
    completed_at = now if new_status == ProjectStatus.SELESAI else None
    repository.set_project_status(project.id, new_status.value, started_at=started_at, completed_at=completed_at)
    repository.add_history(
        StatusHistoryEntry(
            id=str(uuid4()),
            project_id=project.id,
            previous_status=project.status,
            new_status=new_status.value,
            action=action.value,
            change_source=source.value,
            changed_at=now,
            changed_by_user_id=actor_id,
            change_reason=reason,
            reason_code=reason_code,
        )
    )
    return replace(
        project,
        status=new_status.value,
        started_at=started_at or project.started_at,
        completed_at=completed_at or project.completed_at,
    )


def build_detail(repository: WorkflowRepository, context: ProjectContext) -> WorkflowDetail:
    project, agreement = context.project, context.agreement
    history = repository.list_history(project.id)
    has_review = project.status == ProjectStatus.SELESAI and repository.has_freelancer_review(project.id)
    return WorkflowDetail(
        project=project,
        my_party=context.party,
        parties=repository.get_parties(project.umkm_id, agreement.freelancer_id if agreement else None),
        agreement=agreement,
        payment=repository.get_payment(agreement.id) if agreement else None,
        latest_submission=repository.latest_submission(project.id),
        revision_count=repository.count_revision_requests(project.id),
        has_review=has_review,
        history=history,
        available_actions=available_actions(project.status, context.party, agreement, has_review),
        cancellation=_cancellation(project, agreement, history),
    )


def _cancellation(
    project: WorkflowProject, agreement: Agreement | None, history: list[StatusHistoryEntry]
) -> Cancellation | None:
    if project.status != ProjectStatus.DIBATALKAN:
        return None
    entry = next((h for h in reversed(history) if h.new_status == ProjectStatus.DIBATALKAN), None)
    if entry is None:
        return None
    if entry.changed_by_user_id is None:
        by = None
    elif entry.changed_by_user_id == project.umkm_id:
        by = Party.UMKM
    elif agreement is not None and entry.changed_by_user_id == agreement.freelancer_id:
        by = Party.FREELANCER
    else:
        by = None
    return Cancellation(entry.reason_code, entry.change_reason, by, entry.changed_at)


class ApprovalResetter:
    """Kontrak reset_approvals(project_id) untuk modul milestones."""

    def __init__(self, repository: WorkflowRepository, clock: Clock = utc_now):
        self._repository = repository
        self._clock = clock

    def reset(self, project_id: str) -> Agreement:
        # Urutan kunci sama dengan use case lain (project → kesepakatan) agar tidak deadlock.
        self._repository.get_project(project_id, lock=True)
        agreement = self._repository.get_agreement(project_id, lock=True)
        if agreement is None or agreement.status != AgreementStatus.PENDING_APPROVAL:
            raise ConflictError("Kesepakatan sudah final atau belum dibuat")
        updated = replace(
            agreement,
            agreement_version=agreement.agreement_version + 1,
            umkm_approved_at=None,
            freelancer_approved_at=None,
            updated_at=self._clock(),
        )
        self._repository.update_agreement(updated)
        return updated
