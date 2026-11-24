from collections.abc import Callable
from dataclasses import replace
from datetime import UTC

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.modules.milestones.domain.entities import Milestone
from app.modules.milestones.domain.repositories import ProjectMilestoneContext
from app.modules.milestones.infrastructure.models import ProjectMilestoneModel
from app.modules.milestones.infrastructure.repositories import SqlAlchemyMilestoneRepository


class WorkflowMilestoneRepository(SqlAlchemyMilestoneRepository):
    """Repository milestones yang sudah tersambung ke kontrak workflow.

    - freelancer_id dan deadline diambil dari kesepakatan (project_agreements).
    - Penggantian rencana memanggil reset_approvals dalam transaksi yang sama.
    """

    def __init__(self, session: Session, reset_approvals: Callable[[str], object]):
        super().__init__(session=session)
        self._reset_approvals = reset_approvals

    def get_project_context(self, project_id: str) -> ProjectMilestoneContext | None:
        context = super().get_project_context(project_id)
        if context is None:
            return None
        row = self._session.execute(
            text("SELECT freelancer_id, agreed_deadline FROM project_agreements WHERE project_id = :pid"),
            {"pid": project_id},
        ).mappings().first()
        if row is None:
            return context
        return replace(context, freelancer_id=str(row["freelancer_id"]), deadline=row["agreed_deadline"])

    def replace_plan_and_reset_approvals(self, project_id: str, milestones: tuple[Milestone, ...]) -> None:
        # Reset dulu: mengunci baris kesepakatan dan menolak bila sudah final.
        self._reset_approvals(project_id)
        self._session.execute(delete(ProjectMilestoneModel).where(ProjectMilestoneModel.project_id == project_id))
        self._session.flush()
        for item in milestones:
            self._session.add(
                ProjectMilestoneModel(
                    id=item.id,
                    project_id=project_id,
                    name=item.name,
                    description=item.description,
                    weight_percent=item.weight_percent,
                    status=item.status.value,
                    sort_order=item.sort_order,
                    completed_at=item.completed_at.astimezone(UTC).replace(tzinfo=None)
                    if item.completed_at
                    else None,
                    updated_by_user_id=item.updated_by_user_id,
                )
            )
        self._session.flush()
