
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol
from uuid import uuid4

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
    MilestonePlanResult,
    ReplaceMilestonePlanInput,
)

from app.modules.milestones.domain.entities import (
    Milestone,
    MilestoneProgress,
    MilestoneStatus,
    ProjectSchedule,
    DelayRiskResult,
)

from app.modules.milestones.domain.repositories import (
    MilestoneRepository,
    ProjectMilestoneContext,
)

from app.modules.milestones.domain.weight import (
    HUNDRED,
    validate_milestone_plan,
)

from app.modules.milestones.domain.progress import (
    calculate_milestone_progress,
)

from app.modules.milestones.domain.delay_risk import (
    evaluate_delay_risk,
)


# ============================================================
# 1. WORKFLOW PERMISSION CONTRACT
# ============================================================

class MilestoneWorkflowPolicy(Protocol):
    """
    Kontrak pemeriksaan izin dari Workflow Zaid.

    Application tidak boleh menetapkan sendiri
    kapan project boleh diedit/diselesaikan.
    """

    def require_plan_editable(
        self,
        project: ProjectMilestoneContext,
        actor: MilestoneActor,
    ) -> None:
        ...

    def require_completion_allowed(
        self,
        project: ProjectMilestoneContext,
        actor: MilestoneActor,
    ) -> None:
        ...


# ============================================================
# 2. FAIL-CLOSED WORKFLOW POLICY
# ============================================================

class FailClosedMilestoneWorkflowPolicy:
    """
    Policy aman sebelum integrasi Workflow.

    Semua operasi perubahan ditolak.
    Operasi pembacaan tetap diperiksa
    berdasarkan ownership/keanggotaan project.
    """

    def require_plan_editable(
        self,
        project: ProjectMilestoneContext,
        actor: MilestoneActor,
    ) -> None:
        raise ConflictError(
            "Workflow belum mengizinkan "
            "perubahan rencana milestone"
        )

    def require_completion_allowed(
        self,
        project: ProjectMilestoneContext,
        actor: MilestoneActor,
    ) -> None:
        raise ConflictError(
            "Workflow belum mengizinkan "
            "penyelesaian milestone"
        )


# ============================================================
# 3. INPUT VALIDATION
# ============================================================

def _clean_id(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise BadRequestError(
            f"{name} harus berupa string"
        )

    normalized = value.strip()

    if not normalized or len(normalized) > 36:
        raise BadRequestError(
            f"{name} tidak valid"
        )

    return normalized


def _validate_actor(
    actor: MilestoneActor,
) -> MilestoneActor:
    if not isinstance(actor, MilestoneActor):
        raise ForbiddenError(
            "Identitas pengguna tidak valid"
        )

    _clean_id(actor.user_id, "User ID")

    if actor.role not in ("umkm", "freelancer"):
        raise ForbiddenError(
            "Role pengguna tidak diizinkan"
        )

    return actor


def _load_project(
    repository: MilestoneRepository,
    project_id: str,
) -> ProjectMilestoneContext:
    project = repository.get_project_context(
        project_id
    )

    if project is None:
        raise NotFoundError(
            "Project tidak ditemukan"
        )

    return project


def _require_project_access(
    project: ProjectMilestoneContext,
    actor: MilestoneActor,
) -> None:
    """
    Hanya pemilik UMKM atau Freelancer
    yang sudah ditetapkan pada agreement
    yang boleh membaca milestone.

    Freelancer ID harus berasal dari
    agreement resmi, bukan request client.
    """

    _validate_actor(actor)

    owner_allowed = (
        actor.role == "umkm"
        and actor.user_id == project.umkm_id
    )

    freelancer_allowed = (
        actor.role == "freelancer"
        and project.freelancer_id is not None
        and actor.user_id == project.freelancer_id
    )

    if not (owner_allowed or freelancer_allowed):
        raise NotFoundError(
            "Project tidak ditemukan"
        )


def _require_project_owner(
    project: ProjectMilestoneContext,
    actor: MilestoneActor,
) -> None:
    _require_project_access(project, actor)

    if (
        actor.role != "umkm"
        or actor.user_id != project.umkm_id
    ):
        raise ForbiddenError(
            "Hanya pemilik UMKM yang dapat "
            "mengubah rencana milestone"
        )


# ============================================================
# 4. GET MILESTONE PLAN
# ============================================================

class GetMilestonePlan:
    """
    Mengambil rencana milestone suatu project.
    """

    def __init__(
        self,
        repository: MilestoneRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: GetMilestonePlanInput,
    ) -> MilestonePlanResult:

        project_id = _clean_id(
            data.project_id,
            "Project ID",
        )

        project = _load_project(
            self.repository,
            project_id,
        )

        _require_project_access(
            project,
            data.actor,
        )

        items = tuple(
            self.repository.list_milestones(
                project_id
            )
        )

        try:
            total = validate_milestone_plan(items)
        except (TypeError, ValueError) as exc:
            raise ConflictError(
                "Data rencana milestone tidak konsisten"
            ) from exc

        return MilestonePlanResult(
            project_id=project_id,
            items=items,
            total_weight=total,
            is_plan_complete=(total == HUNDRED),
        )


# ============================================================
# 5. GET TOTAL WEIGHT FOR WORKFLOW
# ============================================================

class GetTotalMilestoneWeight:
    """
    Kontrak internal untuk Workflow Zaid.

    Bukan endpoint publik.

    Workflow tetap harus memeriksa aturan
    agreement dan status project sendiri.
    """

    def __init__(
        self,
        repository: MilestoneRepository,
    ):
        self.repository = repository

    def execute(
        self,
        project_id: str,
    ) -> Decimal:

        project_id = _clean_id(
            project_id,
            "Project ID",
        )

        _load_project(
            self.repository,
            project_id,
        )

        total = self.repository.get_total_weight(
            project_id
        )

        if not isinstance(total, Decimal):
            raise ConflictError(
                "Bobot database harus Decimal"
            )

        if (
            not total.is_finite()
            or total < Decimal("0")
            or total > HUNDRED
            or total != total.quantize(
                Decimal("0.01")
            )
        ):
            raise ConflictError(
                "Total bobot milestone tidak valid"
            )

        return total


# ============================================================
# 6. GET MILESTONE PROGRESS
# ============================================================

class GetMilestoneProgress:
    """
    Menghitung progress berbobot
    dari milestone yang tersimpan.
    """

    def __init__(
        self,
        repository: MilestoneRepository,
    ):
        self.repository = repository
        self.get_plan = GetMilestonePlan(
            repository
        )

    def execute(
        self,
        data: GetMilestonePlanInput,
    ) -> MilestoneProgress:

        plan = self.get_plan.execute(data)

        return calculate_milestone_progress(
            plan.project_id,
            plan.items,
        )


# ============================================================
# 7. GET PROJECT DELAY RISK
# ============================================================

class GetProjectDelayRisk:
    """
    Menghitung estimasi risiko keterlambatan
    berdasarkan jadwal dan progres project.
    """

    def __init__(
        self,
        repository: MilestoneRepository,
    ):
        self.repository = repository
        self.get_progress = GetMilestoneProgress(
            repository
        )

    def execute(
        self,
        data: GetDelayRiskInput,
    ) -> DelayRiskResult:

        project_id = _clean_id(
            data.project_id,
            "Project ID",
        )

        progress = self.get_progress.execute(
            GetMilestonePlanInput(
                project_id=project_id,
                actor=data.actor,
            )
        )

        project = _load_project(
            self.repository,
            project_id,
        )

        schedule = ProjectSchedule(
            project_id=project.project_id,
            started_at=project.started_at,
            deadline=project.deadline,
        )

        return evaluate_delay_risk(
            schedule,
            progress,
            data.today,
        )


# ============================================================
# 8. REPLACE MILESTONE PLAN
# ============================================================

class ReplaceMilestonePlan:
    """
    Mengganti seluruh rencana milestone.

    Perubahan hanya diperbolehkan setelah
    Workflow Policy memberi izin.

    Repository wajib mengganti rencana
    dan reset approvals secara atomik.
    """

    def __init__(
        self,
        repository: MilestoneRepository,
        workflow_policy: MilestoneWorkflowPolicy
        | None = None,
    ):
        self.repository = repository

        self.workflow_policy = (
            workflow_policy
            if workflow_policy is not None
            else FailClosedMilestoneWorkflowPolicy()
        )

    def execute(
        self,
        data: ReplaceMilestonePlanInput,
    ) -> MilestonePlanResult:

        project_id = _clean_id(
            data.project_id,
            "Project ID",
        )

        project = _load_project(
            self.repository,
            project_id,
        )

        _require_project_owner(
            project,
            data.actor,
        )

        # Jangan mengubah data sebelum
        # memperoleh izin Workflow.

        self.workflow_policy.require_plan_editable(
            project,
            data.actor,
        )

        if not isinstance(data.items, tuple):
            raise BadRequestError(
                "Items harus berupa tuple"
            )

        milestones: list[Milestone] = []

        for item in data.items:

            if (
                not isinstance(item.name, str)
                or not isinstance(
                    item.description,
                    str,
                )
            ):
                raise BadRequestError(
                    "Nama dan deskripsi harus string"
                )

            milestones.append(
                Milestone(
                    id=str(uuid4()),
                    project_id=project_id,
                    name=item.name.strip(),
                    description=item.description.strip(),
                    weight_percent=item.weight_percent,
                    status=MilestoneStatus.BELUM_SELESAI,
                    sort_order=item.sort_order,
                    completed_at=None,
                    updated_by_user_id=data.actor.user_id,
                )
            )

        items = tuple(milestones)

        try:
            total = validate_milestone_plan(
                items
            )
        except (ValueError, TypeError) as exc:
            raise BadRequestError(
                str(exc)
            ) from exc

        # Replace + reset_approvals:
        # harus dalam transaksi yang sama.
        self.repository.replace_plan_and_reset_approvals(
            project_id,
            items,
        )

        return MilestonePlanResult(
            project_id=project_id,
            items=items,
            total_weight=total,
            is_plan_complete=(total == HUNDRED),
        )


# ============================================================
# 9. COMPLETE MILESTONE
# ============================================================

class CompleteMilestone:
    """
    Menyelesaikan milestone secara idempotent.

    Repository harus memakai UPDATE kondisional
    agar klik bersamaan tidak menambah progres
    dua kali.
    """

    def __init__(
        self,
        repository: MilestoneRepository,
        workflow_policy: MilestoneWorkflowPolicy
        | None = None,
    ):
        self.repository = repository

        self.workflow_policy = (
            workflow_policy
            if workflow_policy is not None
            else FailClosedMilestoneWorkflowPolicy()
        )

        self.get_progress = GetMilestoneProgress(
            repository
        )

    def execute(
        self,
        data: CompleteMilestoneInput,
    ) -> MilestoneProgress:

        project_id = _clean_id(
            data.project_id,
            "Project ID",
        )

        milestone_id = _clean_id(
            data.milestone_id,
            "Milestone ID",
        )

        project = _load_project(
            self.repository,
            project_id,
        )

        _require_project_access(
            project,
            data.actor,
        )

        self.workflow_policy.require_completion_allowed(
            project,
            data.actor,
        )

        existing = tuple(
            self.repository.list_milestones(
                project_id
            )
        )

        target = next(
            (
                item
                for item in existing
                if item.id == milestone_id
            ),
            None,
        )

        if target is None:
            raise NotFoundError(
                "Milestone tidak ditemukan"
            )

        # Permintaan kedua tidak mengubah
        # milestone yang sudah selesai.
        if target.status == MilestoneStatus.SELESAI:
            return self.get_progress.execute(
                GetMilestonePlanInput(
                    project_id,
                    data.actor,
                )
            )

        if target.status != MilestoneStatus.BELUM_SELESAI:
            raise ConflictError(
                "Status milestone tidak valid"
            )

        updated = self.repository.complete_if_pending(
            project_id=project_id,
            milestone_id=milestone_id,
            updated_by_user_id=data.actor.user_id,
            completed_at=datetime.now(timezone.utc),
        )

        if not updated:
            # Baris mungkin sudah diubah request lain.
            # Baca ulang agar respons idempotent.
            latest = tuple(
                self.repository.list_milestones(
                    project_id
                )
            )

            latest_target = next(
                (
                    item
                    for item in latest
                    if item.id == milestone_id
                ),
                None,
            )

            if (
                latest_target is None
                or latest_target.status
                != MilestoneStatus.SELESAI
            ):
                raise ConflictError(
                    "Milestone berubah secara bersamaan"
                )

        return self.get_progress.execute(
            GetMilestonePlanInput(
                project_id=project_id,
                actor=data.actor,
            )
        )