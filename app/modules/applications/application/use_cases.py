from collections.abc import Callable
from uuid import uuid4

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from app.core.unit_of_work import UnitOfWork

from app.modules.applications.application.dto import (
    ApplicationsPage,
    SubmitApplicationInput,
)
from app.modules.applications.domain.entities import (
    APPLICATION_SUBMITTED,
    ProjectApplication,
)
from app.modules.applications.domain.repositories import (
    ApplicationRepository,
)


MAX_PROPOSAL_LENGTH = 5000

MAX_PROPOSED_PRICE = (2**64) - 1
MAX_DURATION_DAYS = (2**32) - 1

MAX_PAGE_LIMIT = 100


def validate_pagination(
    limit: int,
    offset: int,
) -> None:
    if type(limit) is not int:
        raise BadRequestError(
            "Limit harus berupa bilangan bulat"
        )

    if type(offset) is not int:
        raise BadRequestError(
            "Offset harus berupa bilangan bulat"
        )

    if not 1 <= limit <= MAX_PAGE_LIMIT:
        raise BadRequestError(
            "Limit harus berada di antara 1 dan 100"
        )

    if offset < 0:
        raise BadRequestError(
            "Offset tidak boleh negatif"
        )


class SubmitApplication:
    def __init__(
        self,
        repository: ApplicationRepository,
        uow: UnitOfWork,
        on_submitted: Callable[[ProjectApplication], None] | None = None,
    ):
        self._repository = repository
        self._uow = uow
        self._on_submitted = on_submitted

    def execute(
        self,
        freelancer_id: str,
        project_id: str,
        data: SubmitApplicationInput,
    ) -> ProjectApplication:
        if (
            type(data.proposed_price) is not int
            or not (
                1 <= data.proposed_price
                <= MAX_PROPOSED_PRICE
            )
        ):
            raise BadRequestError(
                "Harga penawaran harus berupa bilangan "
                "bulat positif yang valid"
            )

        if (
            type(data.estimated_duration_days) is not int
            or not (
                1 <= data.estimated_duration_days
                <= MAX_DURATION_DAYS
            )
        ):
            raise BadRequestError(
                "Estimasi pengerjaan harus berupa "
                "bilangan hari positif yang valid"
            )

        if not isinstance(data.proposal_message, str):
            raise BadRequestError(
                "Pesan lamaran harus berupa teks"
            )

        proposal_message = (
            data.proposal_message.strip()
        )

        if (
            not proposal_message
            or len(proposal_message) > MAX_PROPOSAL_LENGTH
        ):
            raise BadRequestError(
                "Pesan lamaran wajib diisi dan "
                "maksimal 5000 karakter"
            )

        if not self._repository.freelancer_profile_exists(
            freelancer_id
        ):
            raise NotFoundError(
                "Profil Freelancer tidak ditemukan"
            )

        if not self._repository.project_is_open(
            project_id=project_id,
            lock=True,
        ):
            raise NotFoundError(
                "Proyek tidak tersedia untuk dilamar"
            )

        existing = (
            self._repository.get_by_project_and_freelancer(
                project_id=project_id,
                freelancer_id=freelancer_id,
            )
        )

        if existing is not None:
            raise ConflictError(
                "Kamu sudah pernah melamar proyek ini"
            )

        application = ProjectApplication(
            id=str(uuid4()),
            project_id=project_id,
            freelancer_id=freelancer_id,
            proposed_price=data.proposed_price,
            estimated_duration_days=(
                data.estimated_duration_days
            ),
            proposal_message=proposal_message,
            status=APPLICATION_SUBMITTED,
        )

        saved_application = self._repository.add(
            application
        )

        if self._on_submitted is not None:
            self._on_submitted(saved_application)

        self._uow.commit()

        return saved_application


class GetMyApplications:
    def __init__(
        self,
        repository: ApplicationRepository,
    ):
        self._repository = repository

    def execute(
        self,
        freelancer_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> ApplicationsPage:
        validate_pagination(
            limit=limit,
            offset=offset,
        )

        applications = (
            self._repository.list_by_freelancer(
                freelancer_id=freelancer_id,
                limit=limit + 1,
                offset=offset,
            )
        )

        return ApplicationsPage(
            items=tuple(applications[:limit]),
            limit=limit,
            offset=offset,
            has_more=len(applications) > limit,
        )


class GetProjectApplicants:
    def __init__(
        self,
        repository: ApplicationRepository,
    ):
        self._repository = repository

    def execute(
        self,
        umkm_id: str,
        project_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> ApplicationsPage:
        validate_pagination(
            limit=limit,
            offset=offset,
        )

        if not self._repository.project_owned_by_umkm(
            project_id=project_id,
            umkm_id=umkm_id,
        ):
            raise NotFoundError(
                "Proyek tidak ditemukan"
            )

        applications = self._repository.list_by_project(
            project_id=project_id,
            limit=limit + 1,
            offset=offset,
        )

        return ApplicationsPage(
            items=tuple(applications[:limit]),
            limit=limit,
            offset=offset,
            has_more=len(applications) > limit,
        )
