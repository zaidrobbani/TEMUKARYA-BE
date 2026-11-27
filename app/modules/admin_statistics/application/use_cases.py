from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

from app.modules.admin_statistics.application.dto import (
    AdminProjectPage,
    AdminUserPage,
    GetAdminProjectInput,
    GetAdminStatisticsInput,
    GetAdminUserInput,
    ListAdminProjectsInput,
    ListAdminUsersInput,
)

from app.modules.admin_statistics.domain.entities import (
    AdminActor,
    AdminProjectDetail,
    AdminProjectSummary,
    AdminSystemStatistics,
    AdminUserDetail,
    AdminUserSummary,
)

from app.modules.admin_statistics.domain.repositories import (
    AdminStatisticsRepository,
)

from app.modules.admin_statistics.domain.statistics_rules import (
    build_system_statistics,
    normalize_project_status_filter,
    normalize_search_query,
    normalize_user_role_filter,
    require_admin_actor,
    validate_identifier,
    validate_non_negative_integer,
    validate_pagination,
)


def _require_admin(
    actor: AdminActor,
) -> None:
    try:
        require_admin_actor(actor)

    except PermissionError as exc:
        raise ForbiddenError(
            "Akses hanya diperbolehkan untuk Admin"
        ) from exc


def _validate_identifier(
    value: str,
    field_name: str,
) -> str:
    try:
        return validate_identifier(
            value,
            field_name,
        )

    except ValueError as exc:
        raise BadRequestError(
            str(exc)
        ) from exc


def _validate_filters(
    *,
    search: str | None,
    role: str | None = None,
    status: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    try:
        normalized_search = normalize_search_query(
            search
        )

        normalized_role = normalize_user_role_filter(
            role
        )

        normalized_status = (
            normalize_project_status_filter(
                status
            )
        )

        return (
            normalized_search,
            normalized_role,
            normalized_status,
        )

    except ValueError as exc:
        raise BadRequestError(
            str(exc)
        ) from exc


def _validate_page(
    limit: int,
    offset: int,
) -> None:
    try:
        validate_pagination(
            limit,
            offset,
        )

    except ValueError as exc:
        raise BadRequestError(
            str(exc)
        ) from exc


def _validate_count(
    value: int,
    field_name: str,
) -> int:
    try:
        return validate_non_negative_integer(
            value,
            field_name,
        )

    except ValueError as exc:
        raise ConflictError(
            "Hasil agregasi database tidak valid"
        ) from exc


class ListAdminUsers:
    def __init__(
        self,
        repository: AdminStatisticsRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: ListAdminUsersInput,
    ) -> AdminUserPage:
        _require_admin(
            data.actor
        )

        _validate_page(
            data.limit,
            data.offset,
        )

        search, role, _ = _validate_filters(
            search=data.search,
            role=data.role,
        )

        total = self.repository.count_users(
            role=role,
            search=search,
        )

        total = _validate_count(
            total,
            "total_users",
        )

        items = tuple(
            self.repository.list_users(
                role=role,
                search=search,
                limit=data.limit,
                offset=data.offset,
            )
        )

        if len(items) > data.limit:
            raise ConflictError(
                "Repository mengembalikan "
                "terlalu banyak pengguna"
            )

        for user in items:
            if not isinstance(
                user,
                AdminUserSummary,
            ):
                raise ConflictError(
                    "Data pengguna tidak valid"
                )

            if (
                role is not None
                and user.role.lower() != role
            ):
                raise ConflictError(
                    "Repository mengembalikan "
                    "pengguna dengan role berbeda"
                )

        return AdminUserPage(
            items=items,
            total=total,
            limit=data.limit,
            offset=data.offset,
        )


class GetAdminUser:
    def __init__(
        self,
        repository: AdminStatisticsRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: GetAdminUserInput,
    ) -> AdminUserDetail:
        _require_admin(
            data.actor
        )

        user_id = _validate_identifier(
            data.user_id,
            "User ID",
        )

        result = self.repository.get_user_detail(
            user_id
        )

        if result is None:
            raise NotFoundError(
                "Pengguna tidak ditemukan"
            )

        if (
            not isinstance(result, AdminUserDetail)
            or not isinstance(
                result.user,
                AdminUserSummary,
            )
            or result.user.id != user_id
        ):
            raise ConflictError(
                "Data detail pengguna tidak konsisten"
            )

        role = result.user.role.lower()

        if (
            role == "umkm"
            and result.freelancer_profile is not None
        ):
            raise ConflictError(
                "Profil pengguna tidak sesuai role"
            )

        if (
            role == "freelancer"
            and result.umkm_profile is not None
        ):
            raise ConflictError(
                "Profil pengguna tidak sesuai role"
            )

        if (
            role not in {"umkm", "freelancer"}
            and (
                result.umkm_profile is not None
                or result.freelancer_profile is not None
            )
        ):
            raise ConflictError(
                "Profil pengguna tidak sesuai role"
            )

        return result


class ListAdminProjects:
    def __init__(
        self,
        repository: AdminStatisticsRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: ListAdminProjectsInput,
    ) -> AdminProjectPage:
        _require_admin(
            data.actor
        )

        _validate_page(
            data.limit,
            data.offset,
        )

        search, _, status = _validate_filters(
            search=data.search,
            status=data.status,
        )

        total = self.repository.count_projects(
            status=status,
            search=search,
        )

        total = _validate_count(
            total,
            "total_projects",
        )

        items = tuple(
            self.repository.list_projects(
                status=status,
                search=search,
                limit=data.limit,
                offset=data.offset,
            )
        )

        if len(items) > data.limit:
            raise ConflictError(
                "Repository mengembalikan "
                "terlalu banyak project"
            )

        for project in items:
            if not isinstance(
                project,
                AdminProjectSummary,
            ):
                raise ConflictError(
                    "Data project tidak valid"
                )

            if (
                status is not None
                and project.status.upper() != status
            ):
                raise ConflictError(
                    "Repository mengembalikan "
                    "status project berbeda"
                )

        return AdminProjectPage(
            items=items,
            total=total,
            limit=data.limit,
            offset=data.offset,
        )


class GetAdminProject:
    def __init__(
        self,
        repository: AdminStatisticsRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: GetAdminProjectInput,
    ) -> AdminProjectDetail:
        _require_admin(
            data.actor
        )

        project_id = _validate_identifier(
            data.project_id,
            "Project ID",
        )

        result = self.repository.get_project_detail(
            project_id
        )

        if result is None:
            raise NotFoundError(
                "Project tidak ditemukan"
            )

        if (
            not isinstance(result, AdminProjectDetail)
            or not isinstance(
                result.project,
                AdminProjectSummary,
            )
            or result.project.id != project_id
        ):
            raise ConflictError(
                "Data detail project tidak konsisten"
            )

        return result


class GetAdminStatistics:
    def __init__(
        self,
        repository: AdminStatisticsRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: GetAdminStatisticsInput,
    ) -> AdminSystemStatistics:
        _require_admin(
            data.actor
        )

        result = (
            self.repository.get_system_statistics()
        )

        if not isinstance(
            result,
            AdminSystemStatistics,
        ):
            raise ConflictError(
                "Format statistik database tidak valid"
            )

        try:
            validated = build_system_statistics(
                total_umkm=result.total_umkm,
                total_freelancers=result.total_freelancers,
                total_projects=result.total_projects,
                completed_projects=(
                    result.completed_projects
                ),
                total_transactions=(
                    result.total_transactions
                ),
                platform_income=result.platform_income,
            )

        except ValueError as exc:
            raise ConflictError(
                "Data statistik sistem tidak konsisten"
            ) from exc

        return validated
