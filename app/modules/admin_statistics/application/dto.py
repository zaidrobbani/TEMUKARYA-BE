from dataclasses import dataclass

from app.modules.admin_statistics.domain.entities import (
    AdminActor,
    AdminProjectDetail,
    AdminProjectSummary,
    AdminUserDetail,
    AdminUserSummary,
)


@dataclass(frozen=True, slots=True)
class ListAdminUsersInput:
    actor: AdminActor

    role: str | None = None
    search: str | None = None

    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class AdminUserPage:
    items: tuple[AdminUserSummary, ...]

    total: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class GetAdminUserInput:
    actor: AdminActor
    user_id: str


@dataclass(frozen=True, slots=True)
class ListAdminProjectsInput:
    actor: AdminActor

    status: str | None = None
    search: str | None = None

    limit: int = 20
    offset: int = 0


@dataclass(frozen=True, slots=True)
class AdminProjectPage:
    items: tuple[AdminProjectSummary, ...]

    total: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class GetAdminProjectInput:
    actor: AdminActor
    project_id: str


@dataclass(frozen=True, slots=True)
class GetAdminStatisticsInput:
    actor: AdminActor
