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


# ============================================================
# 1. SHARED HELPERS
# ============================================================

def _require_admin(
    actor: AdminActor,
) -> None:
    """
    Menolak pengguna yang bukan Admin.

    Actor harus berasal dari JWT terverifikasi
    yang disediakan Authentication Module.
    """

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
    """
    Mengubah ValueError dari Domain Layer
    menjadi BadRequestError.
    """

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
    """
    Normalisasi seluruh parameter pencarian.

    Query SQL tetap harus memakai
    parameter binding pada Infrastructure.
    """

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
    """
    Memvalidasi ukuran halaman dan offset.
    """

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
    """
    Memastikan Repository tidak mengembalikan
    nilai COUNT yang tidak valid.
    """

    try:
        return validate_non_negative_integer(
            value,
            field_name,
        )

    except ValueError as exc:
        raise ConflictError(
            "Hasil agregasi database tidak valid"
        ) from exc


# ============================================================
# 2. LIST ADMIN USERS
# ============================================================

class ListAdminUsers:
    """
    Mengambil daftar pengguna yang terdaftar.

    Fitur:
    - TK-F-A-02
    - Pagination
    - Search
    - Filter role
    """

    def __init__(
        self,
        repository: AdminStatisticsRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: ListAdminUsersInput,
    ) -> AdminUserPage:

        # ====================================================
        # 1. ADMIN AUTHORIZATION
        # ====================================================

        _require_admin(
            data.actor
        )

        # ====================================================
        # 2. VALIDATE PAGINATION
        # ====================================================

        _validate_page(
            data.limit,
            data.offset,
        )

        # ====================================================
        # 3. NORMALIZE FILTERS
        # ====================================================

        search, role, _ = _validate_filters(
            search=data.search,
            role=data.role,
        )

        # ====================================================
        # 4. COUNT MATCHING USERS
        # ====================================================

        total = self.repository.count_users(
            role=role,
            search=search,
        )

        total = _validate_count(
            total,
            "total_users",
        )

        # ====================================================
        # 5. FETCH USER LIST
        # ====================================================

        items = tuple(
            self.repository.list_users(
                role=role,
                search=search,
                limit=data.limit,
                offset=data.offset,
            )
        )

        # ====================================================
        # 6. VERIFY REPOSITORY RESULT
        # ====================================================

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

        # ====================================================
        # 7. BUILD RESULT
        # ====================================================

        return AdminUserPage(
            items=items,
            total=total,
            limit=data.limit,
            offset=data.offset,
        )


# ============================================================
# 3. GET ADMIN USER DETAIL
# ============================================================

class GetAdminUser:
    """
    Mengambil detail pengguna dan profilnya.

    Fitur:
    - TK-F-A-03

    Password hash tidak boleh ikut
    dalam entity ataupun response.
    """

    def __init__(
        self,
        repository: AdminStatisticsRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: GetAdminUserInput,
    ) -> AdminUserDetail:

        # ====================================================
        # 1. ADMIN AUTHORIZATION
        # ====================================================

        _require_admin(
            data.actor
        )

        # ====================================================
        # 2. VALIDATE USER ID
        # ====================================================

        user_id = _validate_identifier(
            data.user_id,
            "User ID",
        )

        # ====================================================
        # 3. GET USER DETAIL
        # ====================================================

        result = self.repository.get_user_detail(
            user_id
        )

        if result is None:
            raise NotFoundError(
                "Pengguna tidak ditemukan"
            )

        # ====================================================
        # 4. VERIFY RESULT IDENTITY
        # ====================================================

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

        # ====================================================
        # 5. VERIFY PROFILE ROLE
        # ====================================================

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


# ============================================================
# 4. LIST ADMIN PROJECTS
# ============================================================

class ListAdminProjects:
    """
    Mengambil seluruh Project.

    Fitur:
    - TK-F-A-04
    - Search judul
    - Filter status
    - Pagination

    Project tanpa assigned Freelancer
    tetap harus ditampilkan.
    """

    def __init__(
        self,
        repository: AdminStatisticsRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: ListAdminProjectsInput,
    ) -> AdminProjectPage:

        # ====================================================
        # 1. ADMIN AUTHORIZATION
        # ====================================================

        _require_admin(
            data.actor
        )

        # ====================================================
        # 2. VALIDATE PAGINATION
        # ====================================================

        _validate_page(
            data.limit,
            data.offset,
        )

        # ====================================================
        # 3. NORMALIZE FILTERS
        # ====================================================

        search, _, status = _validate_filters(
            search=data.search,
            status=data.status,
        )

        # ====================================================
        # 4. COUNT MATCHING PROJECTS
        # ====================================================

        total = self.repository.count_projects(
            status=status,
            search=search,
        )

        total = _validate_count(
            total,
            "total_projects",
        )

        # ====================================================
        # 5. FETCH PROJECT LIST
        # ====================================================

        items = tuple(
            self.repository.list_projects(
                status=status,
                search=search,
                limit=data.limit,
                offset=data.offset,
            )
        )

        # ====================================================
        # 6. VERIFY RESULT
        # ====================================================

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

        # ====================================================
        # 7. BUILD RESULT
        # ====================================================

        return AdminProjectPage(
            items=items,
            total=total,
            limit=data.limit,
            offset=data.offset,
        )


# ============================================================
# 5. GET ADMIN PROJECT DETAIL
# ============================================================

class GetAdminProject:
    """
    Mengambil informasi lengkap Project.

    Fitur:
    - TK-F-A-05

    Data meliputi:
    - UMKM pemilik
    - Freelancer yang ditugaskan
    - Budget
    - Harga kesepakatan
    - Deadline dan status
    """

    def __init__(
        self,
        repository: AdminStatisticsRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: GetAdminProjectInput,
    ) -> AdminProjectDetail:

        # ====================================================
        # 1. ADMIN AUTHORIZATION
        # ====================================================

        _require_admin(
            data.actor
        )

        # ====================================================
        # 2. VALIDATE PROJECT ID
        # ====================================================

        project_id = _validate_identifier(
            data.project_id,
            "Project ID",
        )

        # ====================================================
        # 3. GET PROJECT DETAIL
        # ====================================================

        result = self.repository.get_project_detail(
            project_id
        )

        if result is None:
            raise NotFoundError(
                "Project tidak ditemukan"
            )

        # ====================================================
        # 4. VERIFY RESULT IDENTITY
        # ====================================================

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


# ============================================================
# 6. GET SYSTEM STATISTICS
# ============================================================

class GetAdminStatistics:
    """
    Mengambil ringkasan statistik sistem.

    Fitur:
    - TK-F-A-11

    Semua agregasi dihitung Repository.
    Application hanya melakukan otorisasi
    dan validasi hasil.
    """

    def __init__(
        self,
        repository: AdminStatisticsRepository,
    ):
        self.repository = repository

    def execute(
        self,
        data: GetAdminStatisticsInput,
    ) -> AdminSystemStatistics:

        # ====================================================
        # 1. ADMIN AUTHORIZATION
        # ====================================================

        _require_admin(
            data.actor
        )

        # ====================================================
        # 2. FETCH STATISTICS
        # ====================================================

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

        # ====================================================
        # 3. REVALIDATE STATISTICS
        # ====================================================

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