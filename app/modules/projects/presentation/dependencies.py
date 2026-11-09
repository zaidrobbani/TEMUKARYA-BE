from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_uow
from app.core.unit_of_work import UnitOfWork

from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.users.domain.entities import User, UserRole

from app.modules.projects.application.use_cases import GetMyProjects

from app.modules.projects.application.use_cases import (
    CreateProject,
)
from app.modules.projects.domain.repositories import (
    ProjectRepository,
)
from app.modules.projects.infrastructure.repositories import (
    SqlAlchemyProjectRepository,
)

from app.modules.projects.application.use_cases import GetProjectDetail

from app.modules.projects.application.use_cases import UpdateProject

from app.modules.projects.application.use_cases import DeleteProject

from app.modules.projects.application.use_cases import SearchPublicProjects


# 1. AUTHENTICATION
# ============================================================

@dataclass(frozen=True)
class AuthenticatedProjectUser:
    user_id: str
    role: UserRole


def get_authenticated_project_user(
    user: User = Depends(get_current_user),
) -> AuthenticatedProjectUser:
    return AuthenticatedProjectUser(user_id=user.id, role=user.role)


# 2. REPOSITORY DEPENDENCY
# ============================================================

def get_project_repository(
    db: Session = Depends(get_db),
) -> ProjectRepository:
    """
    Menyediakan SQLAlchemy repository
    menggunakan database session FastAPI.
    """
    return SqlAlchemyProjectRepository(db)


# 3. CLOCK
# ============================================================

def _utc_now_naive() -> datetime:
    """
    Waktu UTC tanpa tzinfo untuk kolom
    MySQL DATETIME.

    Kebijakan timezone final perlu
    disepakati bersama tim.
    """
    return datetime.now(timezone.utc).replace(
        tzinfo=None
    )


# 4. CREATE PROJECT USE CASE DEPENDENCY
# ============================================================

def get_create_project_use_case(
    repository: ProjectRepository = Depends(
        get_project_repository
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> CreateProject:
    """
    Menyiapkan dependency CreateProject.
    """

    return CreateProject(
        project_repository=repository,
        uow=uow,
        clock=_utc_now_naive,
    )


def get_my_projects_use_case(
    repository: ProjectRepository = Depends(
        get_project_repository
    ),
) -> GetMyProjects:
    """Dependency untuk mengambil proyek milik UMKM."""

    return GetMyProjects(
        project_repository=repository,
    )


def get_project_detail_use_case(
    repository: ProjectRepository = Depends(
        get_project_repository
    ),
) -> GetProjectDetail:
    return GetProjectDetail(
        project_repository=repository,
    )


def get_update_project_use_case(
    repository: ProjectRepository = Depends(get_project_repository),
    uow: UnitOfWork = Depends(get_uow),
) -> UpdateProject:
    return UpdateProject(
        project_repository=repository,
        uow=uow,
    )



def get_delete_project_use_case(
    repository: ProjectRepository = Depends(
        get_project_repository
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> DeleteProject:
    return DeleteProject(
        project_repository=repository,
        uow=uow,
    )

def get_search_public_projects_use_case(
    repository: ProjectRepository = Depends(
        get_project_repository
    ),
) -> SearchPublicProjects:
    return SearchPublicProjects(
        project_repository=repository,
    )
