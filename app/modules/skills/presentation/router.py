from fastapi import APIRouter, Depends

from app.modules.skills.application.use_cases import (
    ListMasterData,
)
from app.modules.skills.presentation.dependencies import (
    get_master_data_use_case,
)
from app.modules.skills.presentation.schemas import (
    SkillResponse,
    ProjectCategoryResponse,
)


router = APIRouter(tags=["Master Data"])


@router.get(
    "/skills",
    response_model=list[SkillResponse],
)
def get_skills(
    use_case: ListMasterData = Depends(
        get_master_data_use_case
    ),
):
    return use_case.get_skills()


@router.get(
    "/project-categories",
    response_model=list[ProjectCategoryResponse],
)
def get_project_categories(
    use_case: ListMasterData = Depends(
        get_master_data_use_case
    ),
):
    return use_case.get_categories()