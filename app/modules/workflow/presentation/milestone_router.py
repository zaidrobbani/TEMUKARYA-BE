from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.core.dependencies import get_uow
from app.core.responses import ApiResponse, error_responses, success_response
from app.core.unit_of_work import UnitOfWork
from app.modules.milestones.application.dto import (
    CompleteMilestoneInput,
    MilestoneActor,
    MilestoneDraft,
    ReplaceMilestonePlanInput,
)
from app.modules.milestones.domain.repositories import MilestoneRepository
from app.modules.milestones.presentation.dependencies import (
    get_authenticated_milestone_actor,
    get_milestone_repository,
)
from app.modules.milestones.presentation.schemas import MilestonePlanResponse, MilestoneProgressResponse
from app.modules.notifications.application.use_cases import Notifier
from app.modules.notifications.presentation.dependencies import get_notifier
from app.modules.workflow.application.milestone_actions import MarkMilestoneDone, SaveMilestonePlan

router = APIRouter(prefix="/projects", tags=["milestones"])


class MilestoneItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=180)
    description: str = Field("", max_length=2000)
    weight_percent: Decimal = Field(gt=0, le=100, decimal_places=2, description="Bobot (%)")


class MilestonePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MilestoneItemRequest] = Field(max_length=20, description="Urutan list = urutan milestone")


def save_plan_use_case(
    repository: MilestoneRepository = Depends(get_milestone_repository),
    notifier: Notifier = Depends(get_notifier),
    uow: UnitOfWork = Depends(get_uow),
) -> SaveMilestonePlan:
    return SaveMilestonePlan(repository, notifier, uow)


def mark_done_use_case(
    repository: MilestoneRepository = Depends(get_milestone_repository),
    notifier: Notifier = Depends(get_notifier),
    uow: UnitOfWork = Depends(get_uow),
) -> MarkMilestoneDone:
    return MarkMilestoneDone(repository, notifier, uow)


@router.put(
    "/{project_id}/milestones",
    response_model=ApiResponse[MilestonePlanResponse],
    responses=error_responses(400, 401, 403, 404, 409, 422),
    summary="Simpan rencana pengerjaan (draf boleh < 100%). Persetujuan kesepakatan direset",
)
def save_milestone_plan(
    project_id: str,
    body: MilestonePlanRequest,
    actor: MilestoneActor = Depends(get_authenticated_milestone_actor),
    use_case: SaveMilestonePlan = Depends(save_plan_use_case),
):
    data = ReplaceMilestonePlanInput(
        project_id=project_id,
        actor=actor,
        items=tuple(
            MilestoneDraft(
                name=item.name,
                description=item.description,
                weight_percent=item.weight_percent.quantize(Decimal("0.01")),
                sort_order=index,
            )
            for index, item in enumerate(body.items, start=1)
        ),
    )
    result = use_case.execute(data)
    return success_response("Rencana pengerjaan disimpan", MilestonePlanResponse.model_validate(result))


@router.patch(
    "/{project_id}/milestones/{milestone_id}/complete",
    response_model=ApiResponse[MilestoneProgressResponse],
    responses=error_responses(400, 401, 403, 404, 409),
    summary="Freelancer menandai milestone selesai (idempoten)",
)
def complete_milestone(
    project_id: str,
    milestone_id: str,
    actor: MilestoneActor = Depends(get_authenticated_milestone_actor),
    use_case: MarkMilestoneDone = Depends(mark_done_use_case),
):
    progress = use_case.execute(CompleteMilestoneInput(project_id, milestone_id, actor))
    return success_response("Milestone ditandai selesai", MilestoneProgressResponse.model_validate(progress))
