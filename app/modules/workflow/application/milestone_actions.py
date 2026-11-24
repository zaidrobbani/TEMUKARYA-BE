"""Kontrak workflow untuk modul milestones + aksi rencana/penyelesaian milestone yang perlu commit & notifikasi."""

from app.core.exceptions import ConflictError, ForbiddenError
from app.core.unit_of_work import UnitOfWork
from app.modules.milestones.application.dto import (
    CompleteMilestoneInput,
    MilestoneActor,
    MilestonePlanResult,
    ReplaceMilestonePlanInput,
)
from app.modules.milestones.application.use_cases import CompleteMilestone, ReplaceMilestonePlan
from app.modules.milestones.domain.entities import MilestoneProgress, MilestoneStatus
from app.modules.milestones.domain.repositories import MilestoneRepository, ProjectMilestoneContext
from app.modules.notifications.application.use_cases import Notifier
from app.modules.notifications.domain.entities import NotificationType, ReferenceType
from app.modules.users.domain.entities import UserRole
from app.modules.workflow.domain.entities import ProjectStatus
from app.modules.workflow.domain.rules import WORKING_STATUSES

_COMPLETION_BLOCKERS = {
    ProjectStatus.SIAP_DIKERJAKAN: "Tekan Mulai Pengerjaan sebelum menandai milestone",
    ProjectStatus.MENUNGGU_REVIEW: "Milestone tidak dapat diubah saat hasil sedang direview UMKM",
    ProjectStatus.SELESAI: "Proyek sudah selesai, milestone tidak dapat diubah",
    ProjectStatus.DIBATALKAN: "Proyek sudah dibatalkan",
}


class WorkflowMilestonePolicy:
    """Implementasi MilestoneWorkflowPolicy milik modul milestones."""

    def require_plan_editable(self, project: ProjectMilestoneContext, actor: MilestoneActor) -> None:
        if project.status == ProjectStatus.DIBATALKAN:
            raise ConflictError("Proyek sudah dibatalkan")
        if project.status != ProjectStatus.MENUNGGU_KESEPAKATAN:
            raise ConflictError("Rencana pengerjaan hanya dapat diubah sebelum kesepakatan final")

    def require_completion_allowed(self, project: ProjectMilestoneContext, actor: MilestoneActor) -> None:
        if actor.role != UserRole.FREELANCER or actor.user_id != project.freelancer_id:
            raise ForbiddenError("Hanya freelancer terpilih yang dapat menandai milestone selesai")
        if project.status not in WORKING_STATUSES:
            status = ProjectStatus(project.status) if project.status in ProjectStatus else None
            raise ConflictError(
                _COMPLETION_BLOCKERS.get(status, "Milestone hanya dapat ditandai selesai saat proyek dikerjakan")
            )


class SaveMilestonePlan:
    """Simpan Draf / Ajukan rencana: ganti seluruh milestone, persetujuan kesepakatan direset."""

    def __init__(self, repository: MilestoneRepository, notifier: Notifier, uow: UnitOfWork):
        self._repository = repository
        self._use_case = ReplaceMilestonePlan(repository, WorkflowMilestonePolicy())
        self._notifier = notifier
        self._uow = uow

    def execute(self, data: ReplaceMilestonePlanInput) -> MilestonePlanResult:
        result = self._use_case.execute(data)
        project = self._repository.get_project_context(data.project_id)
        other = project.freelancer_id if data.actor.user_id == project.umkm_id else project.umkm_id
        if other is not None:
            self._notifier.notify(
                other,
                NotificationType.AGREEMENT_UPDATED,
                "Rencana pengerjaan diperbarui",
                f"Total bobot {result.total_weight.normalize():f}%. Periksa lalu tekan Lanjut Project",
                ReferenceType.PROJECT,
                data.project_id,
            )
        self._uow.commit()
        return result


class MarkMilestoneDone:
    """Tandai Selesai: idempoten, UMKM diberi tahu hanya saat status benar-benar berubah."""

    def __init__(self, repository: MilestoneRepository, notifier: Notifier, uow: UnitOfWork):
        self._repository = repository
        self._use_case = CompleteMilestone(repository, WorkflowMilestonePolicy())
        self._notifier = notifier
        self._uow = uow

    def execute(self, data: CompleteMilestoneInput) -> MilestoneProgress:
        before = {m.id: m for m in self._repository.list_milestones(data.project_id)}
        progress = self._use_case.execute(data)
        target = before.get(data.milestone_id)
        if target is not None and target.status == MilestoneStatus.BELUM_SELESAI:
            project = self._repository.get_project_context(data.project_id)
            self._notifier.notify(
                project.umkm_id,
                NotificationType.MILESTONE_COMPLETED,
                "Milestone selesai",
                f"{target.name} ditandai selesai, progres kini {progress.progress_percent.normalize():f}%",
                ReferenceType.PROJECT,
                data.project_id,
            )
        self._uow.commit()
        return progress
