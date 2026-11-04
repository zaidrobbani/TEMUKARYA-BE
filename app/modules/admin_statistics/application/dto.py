from dataclasses import dataclass

from app.modules.admin_statistics.domain.entities import (
    AdminActor,
    AdminProjectDetail,
    AdminProjectSummary,
    AdminUserDetail,
    AdminUserSummary,
)


# ============================================================
# 1. LIST ADMIN USERS
# ============================================================

@dataclass(frozen=True, slots=True)
class ListAdminUsersInput:
    """
    Input untuk mengambil daftar pengguna.

    Mendukung:
    - Filter role
    - Search nama atau email
    - Pagination
    """

    actor: AdminActor

    role: str | None = None
    search: str | None = None

    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class AdminUserPage:
    """
    Hasil daftar pengguna beserta pagination.
    """

    items: tuple[AdminUserSummary, ...]

    total: int
    limit: int
    offset: int


# ============================================================
# 2. GET ADMIN USER DETAIL
# ============================================================

@dataclass(frozen=True, slots=True)
class GetAdminUserInput:
    """
    Input untuk mengambil detail pengguna.
    """

    actor: AdminActor
    user_id: str


# ============================================================
# 3. LIST ADMIN PROJECTS
# ============================================================

@dataclass(frozen=True, slots=True)
class ListAdminProjectsInput:
    """
    Input untuk mengambil seluruh Project.

    Mendukung:
    - Filter status
    - Search judul Project
    - Pagination
    """

    actor: AdminActor

    status: str | None = None
    search: str | None = None

    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class AdminProjectPage:
    """
    Hasil daftar Project beserta pagination.
    """

    items: tuple[AdminProjectSummary, ...]

    total: int
    limit: int
    offset: int


# ============================================================
# 4. GET ADMIN PROJECT DETAIL
# ============================================================

@dataclass(frozen=True, slots=True)
class GetAdminProjectInput:
    """
    Input untuk mengambil detail Project.
    """

    actor: AdminActor
    project_id: str


# ============================================================
# 5. GET SYSTEM STATISTICS
# ============================================================

@dataclass(frozen=True, slots=True)
class GetAdminStatisticsInput:
    """
    Input untuk mengambil statistik sistem.

    Tidak membutuhkan parameter filter.

    AdminActor diperlukan untuk authorization.
    """

    actor: AdminActor