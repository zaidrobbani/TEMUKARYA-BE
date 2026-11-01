from typing import Protocol

from app.modules.applications.domain.entities import (
    ProjectApplication,
)


class ApplicationRepository(Protocol):
    """
    Kontrak akses data Project Applications.
    """

    def freelancer_profile_exists(
        self,
        freelancer_id: str,
    ) -> bool:
        ...

    def project_is_open(
        self,
        project_id: str,
        lock: bool = False,
    ) -> bool:
        ...

    def project_owned_by_umkm(
        self,
        project_id: str,
        umkm_id: str,
    ) -> bool:
        ...

    def add(
        self,
        application: ProjectApplication,
    ) -> ProjectApplication:
        ...

    def get_by_id(
        self,
        application_id: str,
    ) -> ProjectApplication | None:
        ...

    def get_by_project_and_freelancer(
        self,
        project_id: str,
        freelancer_id: str,
    ) -> ProjectApplication | None:
        ...

    def list_by_freelancer(
        self,
        freelancer_id: str,
        limit: int,
        offset: int,
    ) -> list[ProjectApplication]:
        ...

    def list_by_project(
        self,
        project_id: str,
        limit: int,
        offset: int,
    ) -> list[ProjectApplication]:
        ...
