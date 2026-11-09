from fastapi import APIRouter, Depends

from app.core.responses import ApiResponse, success_response
from app.modules.skills.application.use_cases import ListMasterData
from app.modules.skills.presentation.dependencies import get_master_data_use_case
from app.modules.skills.presentation.schemas import ProjectCategoryResponse, SkillResponse

router = APIRouter(tags=["Master Data"])


@router.get("/skills", response_model=ApiResponse[list[SkillResponse]])
def get_skills(use_case: ListMasterData = Depends(get_master_data_use_case)):
    return success_response("Daftar skill berhasil diambil", use_case.get_skills())


@router.get("/project-categories", response_model=ApiResponse[list[ProjectCategoryResponse]])
def get_project_categories(use_case: ListMasterData = Depends(get_master_data_use_case)):
    return success_response("Daftar kategori project berhasil diambil", use_case.get_categories())
