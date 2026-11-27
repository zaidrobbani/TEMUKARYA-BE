from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.responses import ApiResponse, SuccessBody, error_responses, success_response

from app.modules.milestones.application.dto import (
    GetDelayRiskInput,
    GetMilestonePlanInput,
    MilestoneActor,
)

from app.modules.milestones.application.use_cases import (
    GetMilestonePlan,
    GetMilestoneProgress,
    GetProjectDelayRisk,
)

from app.modules.milestones.infrastructure.repositories import (
    SqlAlchemyMilestoneRepository,
)

from app.modules.milestones.presentation.dependencies import (
    get_authenticated_milestone_actor,
    get_milestone_repository,
    get_milestone_today,
)

from app.modules.milestones.presentation.schemas import (
    MilestoneDelayRiskResponse,
    MilestonePlanResponse,
    MilestoneProgressResponse,
)


router = APIRouter(
    prefix="/projects",
    tags=["milestones"],
)


@router.get(
    "/{project_id}/milestones",
    response_model=ApiResponse[MilestonePlanResponse],
    responses=error_responses(400, 401, 403, 404),
)
def get_project_milestones(
    project_id: str,
    actor: Annotated[
        MilestoneActor,
        Depends(get_authenticated_milestone_actor),
    ],
    repository: Annotated[
        SqlAlchemyMilestoneRepository,
        Depends(get_milestone_repository),
    ],
) -> SuccessBody[MilestonePlanResponse]:
    use_case = GetMilestonePlan(
        repository
    )

    result = use_case.execute(
        GetMilestonePlanInput(
            project_id=project_id,
            actor=actor,
        )
    )

    return success_response(
        "Daftar milestone berhasil diambil",
        MilestonePlanResponse.model_validate(result),
    )


@router.get(
    "/{project_id}/milestones/progress",
    response_model=ApiResponse[MilestoneProgressResponse],
    responses=error_responses(400, 401, 403, 404),
)
def get_project_milestone_progress(
    project_id: str,
    actor: Annotated[
        MilestoneActor,
        Depends(get_authenticated_milestone_actor),
    ],
    repository: Annotated[
        SqlAlchemyMilestoneRepository,
        Depends(get_milestone_repository),
    ],
) -> SuccessBody[MilestoneProgressResponse]:
    use_case = GetMilestoneProgress(
        repository
    )

    result = use_case.execute(
        GetMilestonePlanInput(
            project_id=project_id,
            actor=actor,
        )
    )

    return success_response(
        "Progres milestone berhasil diambil",
        MilestoneProgressResponse.model_validate(result),
    )


@router.get(
    "/{project_id}/milestones/delay-risk",
    response_model=ApiResponse[MilestoneDelayRiskResponse],
    responses=error_responses(400, 401, 403, 404),
)
def get_project_milestone_delay_risk(
    project_id: str,
    actor: Annotated[
        MilestoneActor,
        Depends(get_authenticated_milestone_actor),
    ],
    repository: Annotated[
        SqlAlchemyMilestoneRepository,
        Depends(get_milestone_repository),
    ],
    today: Annotated[
        date,
        Depends(get_milestone_today),
    ],
) -> SuccessBody[MilestoneDelayRiskResponse]:
    use_case = GetProjectDelayRisk(
        repository
    )

    result = use_case.execute(
        GetDelayRiskInput(
            project_id=project_id,
            actor=actor,
            today=today,
        )
    )

    return success_response(
        "Risiko keterlambatan berhasil dihitung",
        MilestoneDelayRiskResponse.model_validate(result),
    )
