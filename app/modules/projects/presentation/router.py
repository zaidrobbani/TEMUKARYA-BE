from fastapi import APIRouter, Depends, Query, status

from app.core.exceptions import BadRequestError, ForbiddenError
from app.core.responses import ApiResponse, error_responses, success_response
from app.modules.users.domain.entities import UserRole

from app.modules.projects.application.use_cases import GetMyProjects
from app.modules.projects.presentation.dependencies import get_my_projects_use_case

from app.modules.projects.application.use_cases import GetProjectDetail
from app.modules.projects.presentation.dependencies import get_project_detail_use_case

from app.modules.projects.application.dto import UpdateProjectInput
from app.modules.projects.application.use_cases import UpdateProject
from app.modules.projects.presentation.dependencies import get_update_project_use_case
from app.modules.projects.presentation.schemas import UpdateProjectRequest

from app.modules.projects.application.dto import CreateProjectInput
from app.modules.projects.application.use_cases import CreateProject
from app.modules.projects.presentation.dependencies import (
    AuthenticatedProjectUser,
    get_authenticated_project_user,
    get_create_project_use_case,
)
from app.modules.projects.presentation.schemas import (
    CreateProjectRequest,
    ProjectResponse,
)

from app.modules.projects.application.use_cases import DeleteProject
from app.modules.projects.presentation.dependencies import (
    get_delete_project_use_case,
)

from app.modules.projects.application.use_cases import SearchPublicProjects
from app.modules.projects.presentation.dependencies import get_search_public_projects_use_case
from app.modules.projects.presentation.schemas import PublicProjectsPageResponse


router = APIRouter(
    prefix="/projects",
    tags=["projects"],
)


@router.post(
    "",
    response_model=ApiResponse[ProjectResponse],
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 401, 403, 422),
    summary="Create Project",
    description="UMKM membuat dan memublikasikan proyek baru.",
)
def create_project(
    body: CreateProjectRequest,
    current_user: AuthenticatedProjectUser = Depends(
        get_authenticated_project_user
    ),
    use_case: CreateProject = Depends(
        get_create_project_use_case
    ),
):
    """
    Membuat proyek baru.

    Hanya UMKM yang terautentikasi dapat
    menggunakan endpoint ini.
    """

    # 1. Authorization: hanya role UMKM
    if current_user.role != UserRole.UMKM:
        raise ForbiddenError(
            "Hanya pengguna UMKM yang dapat membuat proyek"
        )

    # 2. Ubah Pydantic Request menjadi Application DTO
    data = CreateProjectInput(
        category_id=body.category_id,
        title=body.title,
        description=body.description,
        budget=body.budget,
        deadline=body.deadline,
        skill_ids=tuple(body.skill_ids),
    )

    # 3. Jalankan business logic
    try:
        project = use_case.execute(
            umkm_id=current_user.user_id,
            data=data,
        )
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc

    # 4. Kembalikan informasi proyek
    return success_response("Project berhasil dibuat", ProjectResponse.model_validate(project))



@router.get(
    "/mine",
    response_model=ApiResponse[list[ProjectResponse]],
    responses=error_responses(401, 403),
    summary="Get My Projects",
    description="UMKM melihat daftar proyek miliknya sendiri.",
)
def get_my_projects(
    current_user: AuthenticatedProjectUser = Depends(
        get_authenticated_project_user
    ),
    use_case: GetMyProjects = Depends(
        get_my_projects_use_case
    ),
):

    # Hanya UMKM yang memiliki akses
    if current_user.role != UserRole.UMKM:
        raise ForbiddenError(
            "Hanya pengguna UMKM yang dapat melihat proyek miliknya"
        )

    # Identitas berasal dari authentication dependency
    projects = use_case.execute(
        umkm_id=current_user.user_id
    )

    return success_response(
        "Daftar project berhasil diambil",
        [ProjectResponse.model_validate(project) for project in projects],
    )



@router.get(
    "/{project_id}",
    response_model=ApiResponse[ProjectResponse],
    responses=error_responses(401, 404),
    summary="Get Project Detail",
    description="Melihat detail proyek berdasarkan ID.",
)
def get_project_detail(
    project_id: str,
    current_user: AuthenticatedProjectUser = Depends(
        get_authenticated_project_user
    ),
    use_case: GetProjectDetail = Depends(
        get_project_detail_use_case
    ),
):

    project = use_case.execute(
        project_id=project_id,
        requester_id=current_user.user_id,
    )

    return success_response("Detail project berhasil diambil", ProjectResponse.model_validate(project))


# ============================================================
# UPDATE PROJECT
# ============================================================

@router.put(
    "/{project_id}",
    response_model=ApiResponse[ProjectResponse],
    responses=error_responses(400, 401, 403, 404, 409, 422),
    summary="Update Project",
    description="UMKM memperbarui proyek miliknya sebelum pengerjaan.",
)
def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    current_user: AuthenticatedProjectUser = Depends(
        get_authenticated_project_user
    ),
    use_case: UpdateProject = Depends(
        get_update_project_use_case
    ),
):

    # 1. Hanya UMKM yang boleh memperbarui proyek.
    if current_user.role != UserRole.UMKM:
        raise ForbiddenError(
            "Hanya pengguna UMKM yang dapat memperbarui proyek"
        )

    # 2. Ubah request menjadi Application DTO.
    data = UpdateProjectInput(
        category_id=body.category_id,
        title=body.title,
        description=body.description,
        budget=body.budget,
        deadline=body.deadline,
        skill_ids=tuple(body.skill_ids),
    )

    # 3. Jalankan business logic.
    try:
        project = use_case.execute(
            umkm_id=current_user.user_id,
            project_id=project_id,
            data=data,
        )
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc

    # 4. Kembalikan proyek yang sudah diperbarui.
    return success_response("Project berhasil diperbarui", ProjectResponse.model_validate(project))



@router.delete(
    "/{project_id}",
    response_model=ApiResponse[None],
    responses=error_responses(401, 403, 404, 409),
    summary="Delete Project",
    description="UMKM menghapus proyek miliknya sebelum pengerjaan.",
)
def delete_project(
    project_id: str,
    current_user: AuthenticatedProjectUser = Depends(
        get_authenticated_project_user
    ),
    use_case: DeleteProject = Depends(
        get_delete_project_use_case
    ),
):

    if current_user.role != UserRole.UMKM:
        raise ForbiddenError(
            "Hanya pengguna UMKM yang dapat menghapus proyek"
        )

    use_case.execute(
        umkm_id=current_user.user_id,
        project_id=project_id,
    )

    return success_response("Project berhasil dihapus")


@router.get(
    "",
    response_model=ApiResponse[PublicProjectsPageResponse],
    responses=error_responses(400, 401, 403, 422),
    summary="Search Public Projects",
    description="Freelancer mencari proyek terbuka dengan filter.",
)
def search_public_projects(
    search: str | None = Query(
        default=None,
        max_length=100,
    ),
    category_id: str | None = Query(
        default=None,
        max_length=50,
    ),
    min_budget: int | None = Query(
        default=None,
        ge=0,
    ),
    max_budget: int | None = Query(
        default=None,
        ge=0,
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
        le=10000,
    ),
    current_user: AuthenticatedProjectUser = Depends(
        get_authenticated_project_user
    ),
    use_case: SearchPublicProjects = Depends(
        get_search_public_projects_use_case
    ),
):

    if current_user.role != UserRole.FREELANCER:
        raise ForbiddenError(
            "Hanya Freelancer yang dapat mencari proyek"
        )

    try:
        result = use_case.execute(
            search=search,
            category_id=category_id,
            min_budget=min_budget,
            max_budget=max_budget,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc

    return success_response(
        "Daftar project berhasil diambil",
        PublicProjectsPageResponse(
            items=[
                ProjectResponse.model_validate(project)
                for project in result.items
            ],
            limit=result.limit,
            offset=result.offset,
            has_more=result.has_more,
        ),
    )

# Project Attachment HTTP Endpoints
from app.modules.projects.presentation.attachment_router import router as project_attachment_router
router.include_router(project_attachment_router)