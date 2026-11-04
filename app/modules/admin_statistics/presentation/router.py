
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
)

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


# ============================================================
# 1. ROUTER CONFIGURATION
# ============================================================

router = APIRouter(
    prefix="/admin",
    tags=["admin-statistics"],
)


# ============================================================
# 2. LIST USERS
# TK-F-A-02
# ============================================================

@router.get(
    "/users",
    response_model=AdminUserPageResponse,
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
):
    """
    Mengambil daftar pengguna.

    Mendukung:
    - Role filtering
    - Search by name/email
    - Pagination

    Admin authorization dilakukan
    oleh Application Layer.
    """

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

    return AdminUserPageResponse.model_validate(
        result
    )


# ============================================================
# 3. GET USER DETAIL
# TK-F-A-03
# ============================================================

@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetailResponse,
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
):
    """
    Mengambil detail satu pengguna.

    UMKM:
        Menampilkan profil UMKM.

    Freelancer:
        Menampilkan profil Freelancer.

    Password hash tidak dikirim.
    """

    use_case = GetAdminUser(
        repository
    )

    result = use_case.execute(
        GetAdminUserInput(
            actor=actor,
            user_id=user_id,
        )
    )

    return AdminUserDetailResponse.model_validate(
        result
    )


# ============================================================
# 4. LIST PROJECTS
# TK-F-A-04
# ============================================================

@router.get(
    "/projects",
    response_model=AdminProjectPageResponse,
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
):
    """
    Mengambil seluruh Project.

    Project tanpa Freelancer tetap
    ditampilkan.

    Mendukung:
    - Filter status
    - Search title
    - Pagination
    """

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

    return AdminProjectPageResponse.model_validate(
        result
    )


# ============================================================
# 5. GET PROJECT DETAIL
# TK-F-A-05
# ============================================================

@router.get(
    "/projects/{project_id}",
    response_model=AdminProjectDetailResponse,
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
):
    """
    Mengambil detail sebuah Project.

    Menampilkan:
    - UMKM pemilik
    - Freelancer yang ditugaskan
    - Budget
    - Agreed price
    - Deadline
    - Status
    """

    use_case = GetAdminProject(
        repository
    )

    result = use_case.execute(
        GetAdminProjectInput(
            actor=actor,
            project_id=project_id,
        )
    )

    return AdminProjectDetailResponse.model_validate(
        result
    )


# ============================================================
# 6. GET SYSTEM STATISTICS
# TK-F-A-11
# ============================================================

@router.get(
    "/statistics",
    response_model=AdminSystemStatisticsResponse,
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
):
    """
    Mengambil ringkasan statistik TEMUKARYA.

    Statistik:
    - Total UMKM
    - Total Freelancer
    - Total Project
    - Total Project Selesai
    - Total Transaksi
    - Platform Income

    Hanya Admin yang diizinkan.
    """

    use_case = GetAdminStatistics(
        repository
    )

    result = use_case.execute(
        GetAdminStatisticsInput(
            actor=actor
        )
    )

    return AdminSystemStatisticsResponse.model_validate(
        result
    )