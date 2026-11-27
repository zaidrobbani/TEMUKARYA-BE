from typing import Protocol

from app.modules.admin_statistics.domain.entities import (
    AdminProjectDetail,
    AdminProjectSummary,
    AdminSystemStatistics,
    AdminUserDetail,
    AdminUserSummary,
)


class AdminStatisticsRepository(Protocol):
    def list_users(
        self,
        *,
        role: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[AdminUserSummary, ...]:
        ...

    def count_users(
        self,
        *,
        role: str | None,
        search: str | None,
    ) -> int:
        ...

    def get_user_detail(
        self,
        user_id: str,
    ) -> AdminUserDetail | None:
        ...

    def list_projects(
        self,
        *,
        status: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[AdminProjectSummary, ...]:
        ...

    def count_projects(
        self,
        *,
        status: str | None,
        search: str | None,
    ) -> int:
        ...

    def get_project_detail(
        self,
        project_id: str,
    ) -> AdminProjectDetail | None:
        ...

    def get_system_statistics(
        self,
    ) -> AdminSystemStatistics:
        ...
