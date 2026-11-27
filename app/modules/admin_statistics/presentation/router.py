from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
)

from app.core.responses import ApiResponse, SuccessBody, error_responses, success_response

from app.modules.admin_statistics.application.dto import (
    GetAdminProjectInput,
    GetAdminStatisticsInput,
    GetAdminUserInput,
    ListAdminProjectsInput,
    ListAdminUsersInput,
)

from app.modules.admin_statistics.application.use_cases import (
    GetAdminProject,
    GetAdminStatistics,
    GetAdminUser,
    ListAdminProjects,
    ListAdminUsers,
)

from app.modules.admin_statistics.domain.entities import (
    AdminActor,
)

from app.modules.admin_statistics.infrastructure.repositories import (
    SqlAlchemyAdminStatisticsRepository,
)

from app.modules.admin_statistics.presentation.dependencies import (
    get_admin_statistics_repository,
    get_authenticated_admin_actor,
)

from app.modules.admin_statistics.presentation.schemas import (
    AdminProjectDetailResponse,
    AdminProjectPageResponse,
    AdminSystemStatisticsResponse,
    AdminUserDetailResponse,
    AdminUserPageResponse,
)


router = APIRouter(
    prefix="/admin",
    tags=["admin-statistics"],
)


@router.get(
    "/users",
    response_model=ApiResponse[AdminUserPageResponse],
    responses=error_responses(400, 401, 403, 422),
)
def list_admin_users(
    actor: Annotated[
        AdminActor,
        Depends(get_authenticated_admin_actor),
    ],
    repository: Annotated[
        SqlAlchemyAdminStatisticsRepository,
        Depends(get_admin_statistics_repository),
    ],
    role: str | None = Query(
        default=None,
        max_length=20,
    ),
    search: str | None = Query(
        default=None,
        max_length=100,
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
) -> SuccessBody[AdminUserPageResponse]:
    use_case = ListAdminUsers(
        repository
    )

    result = use_case.execute(
        ListAdminUsersInput(
            actor=actor,
            role=role,
            search=search,
            limit=limit,
            offset=offset,
        )
    )

    return success_response(
        "Daftar pengguna berhasil diambil",
        AdminUserPageResponse.model_validate(result),
    )


@router.get(
    "/users/{user_id}",
    response_model=ApiResponse[AdminUserDetailResponse],
    responses=error_responses(400, 401, 403, 404, 409),
)
def get_admin_user_detail(
    user_id: str,
    actor: Annotated[
        AdminActor,
        Depends(get_authenticated_admin_actor),
    ],
    repository: Annotated[
        SqlAlchemyAdminStatisticsRepository,
        Depends(get_admin_statistics_repository),
    ],
) -> SuccessBody[AdminUserDetailResponse]:
    use_case = GetAdminUser(
        repository
    )

    result = use_case.execute(
        GetAdminUserInput(
            actor=actor,
            user_id=user_id,
        )
    )

    return success_response(
        "Detail pengguna berhasil diambil",
        AdminUserDetailResponse.model_validate(result),
    )


@router.get(
    "/projects",
    response_model=ApiResponse[AdminProjectPageResponse],
    responses=error_responses(400, 401, 403, 422),
)
def list_admin_projects(
    actor: Annotated[
        AdminActor,
        Depends(get_authenticated_admin_actor),
    ],
    repository: Annotated[
        SqlAlchemyAdminStatisticsRepository,
        Depends(get_admin_statistics_repository),
    ],
    status: str | None = Query(
        default=None,
        max_length=40,
    ),
    search: str | None = Query(
        default=None,
        max_length=100,
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
) -> SuccessBody[AdminProjectPageResponse]:
    use_case = ListAdminProjects(
        repository
    )

    result = use_case.execute(
        ListAdminProjectsInput(
            actor=actor,
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )
    )

    return success_response(
        "Daftar project berhasil diambil",
        AdminProjectPageResponse.model_validate(result),
    )


@router.get(
    "/projects/{project_id}",
    response_model=ApiResponse[AdminProjectDetailResponse],
    responses=error_responses(400, 401, 403, 404, 409),
)
def get_admin_project_detail(
    project_id: str,
    actor: Annotated[
        AdminActor,
        Depends(get_authenticated_admin_actor),
    ],
    repository: Annotated[
        SqlAlchemyAdminStatisticsRepository,
        Depends(get_admin_statistics_repository),
    ],
) -> SuccessBody[AdminProjectDetailResponse]:
    use_case = GetAdminProject(
        repository
    )

    result = use_case.execute(
        GetAdminProjectInput(
            actor=actor,
            project_id=project_id,
        )
    )

    return success_response(
        "Detail project berhasil diambil",
        AdminProjectDetailResponse.model_validate(result),
    )


@router.get(
    "/statistics",
    response_model=ApiResponse[AdminSystemStatisticsResponse],
    responses=error_responses(401, 403, 409),
)
def get_admin_system_statistics(
    actor: Annotated[
        AdminActor,
        Depends(get_authenticated_admin_actor),
    ],
    repository: Annotated[
        SqlAlchemyAdminStatisticsRepository,
        Depends(get_admin_statistics_repository),
    ],
) -> SuccessBody[AdminSystemStatisticsResponse]:
    use_case = GetAdminStatistics(
        repository
    )

    result = use_case.execute(
        GetAdminStatisticsInput(
            actor=actor
        )
    )

    return success_response(
        "Statistik sistem berhasil diambil",
        AdminSystemStatisticsResponse.model_validate(result),
    )
