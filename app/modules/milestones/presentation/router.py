from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

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


# ============================================================
# ROUTER CONFIGURATION
# ============================================================

router = APIRouter(
    prefix="/projects",
    tags=["milestones"],
)


# ============================================================
# 1. GET PROJECT MILESTONE PLAN
# ============================================================

@router.get(
    "/{project_id}/milestones",
    response_model=MilestonePlanResponse,
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
):
    """
    Mengambil daftar milestone satu project.

    Akses:
    - UMKM pemilik project
    - Freelancer yang ditugaskan
    """

    use_case = GetMilestonePlan(
        repository
    )

    result = use_case.execute(
        GetMilestonePlanInput(
            project_id=project_id,
            actor=actor,
        )
    )

    return MilestonePlanResponse.model_validate(
        result
    )


# ============================================================
# 2. GET PROJECT MILESTONE PROGRESS
# ============================================================

@router.get(
    "/{project_id}/milestones/progress",
    response_model=MilestoneProgressResponse,
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
):
    """
    Mengembalikan:
    - Total bobot
    - Bobot selesai
    - Bobot tersisa
    - Persentase progres project
    """

    use_case = GetMilestoneProgress(
        repository
    )

    result = use_case.execute(
        GetMilestonePlanInput(
            project_id=project_id,
            actor=actor,
        )
    )

    return MilestoneProgressResponse.model_validate(
        result
    )


# ============================================================
# 3. GET PROJECT DELAY RISK
# ============================================================

@router.get(
    "/{project_id}/milestones/delay-risk",
    response_model=MilestoneDelayRiskResponse,
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
):
    """
    Menghitung risiko keterlambatan.

    Tanggal bersumber dari server,
    bukan dari request pengguna.
    """

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

    return MilestoneDelayRiskResponse.model_validate(
        result
    )