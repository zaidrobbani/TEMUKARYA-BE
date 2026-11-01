
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_uow
from app.core.exceptions import UnauthorizedError
from app.core.unit_of_work import UnitOfWork

from app.modules.users.domain.entities import UserRole

from app.modules.applications.application.use_cases import (
    GetMyApplications,
    GetProjectApplicants,
    SubmitApplication,
)

from app.modules.applications.domain.repositories import (
    ApplicationRepository,
)

from app.modules.applications.infrastructure.repositories import (
    SqlAlchemyApplicationRepository,
)


# ============================================================
# AUTHENTICATED APPLICATION USER
# ============================================================

@dataclass(frozen=True)
class AuthenticatedApplicationUser:
    user_id: str
    role: UserRole


def get_authenticated_application_user(
) -> AuthenticatedApplicationUser:
    """
    Fail-closed sampai Auth/JWT Zaid terintegrasi.

    Tidak membuat identitas user palsu.
    Tidak mengambil user_id dari request body.

    Saat integrasi JWT siap, dependency ini
    akan dihubungkan ke kontrak Auth tim.
    """
    raise UnauthorizedError(
        "Authentication belum terintegrasi"
    )


# ============================================================
# REPOSITORY DEPENDENCY
# ============================================================

def get_application_repository(
    db: Session = Depends(get_db),
) -> ApplicationRepository:
    return SqlAlchemyApplicationRepository(db)


# ============================================================
# SUBMIT APPLICATION DEPENDENCY
# ============================================================

def get_submit_application_use_case(
    repository: ApplicationRepository = Depends(
        get_application_repository
    ),
    uow: UnitOfWork = Depends(get_uow),
) -> SubmitApplication:

    return SubmitApplication(
        repository=repository,
        uow=uow,
    )


# ============================================================
# GET MY APPLICATIONS DEPENDENCY
# ============================================================

def get_my_applications_use_case(
    repository: ApplicationRepository = Depends(
        get_application_repository
    ),
) -> GetMyApplications:

    return GetMyApplications(
        repository=repository,
    )


# ============================================================
# GET PROJECT APPLICANTS DEPENDENCY
# ============================================================

def get_project_applicants_use_case(
    repository: ApplicationRepository = Depends(
        get_application_repository
    ),
) -> GetProjectApplicants:

    return GetProjectApplicants(
        repository=repository,
    )
