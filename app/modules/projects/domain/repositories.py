from typing import Protocol

from app.modules.projects.domain.entities import Project


class ProjectRepository(Protocol):

    # PROJECT CRUD

    def add(self, project: Project) -> Project:
        """Menyimpan project baru."""
        ...

    def get_by_id(self, project_id: str) -> Project | None:
        """Mengambil project berdasarkan UUID."""
        ...

    def list_by_umkm_id(self, umkm_id: str) -> list[Project]:
        """Mengambil daftar project milik UMKM."""
        ...

    def update(
        self,
        project: Project,
        skill_ids: tuple[str, ...],
    ) -> Project | None:
        ...

    def delete(
        self,
        project_id: str,
        umkm_id: str,
    ) -> bool:
        ...

    def search_public(
        self,
        search: str | None,
        category_id: str | None,
        min_budget: int | None,
        max_budget: int | None,
        limit: int,
        offset: int,
    ) -> list[Project]:
        ...



    # BUSINESS VALIDATION QUERIES

    def umkm_profile_exists(self, umkm_id: str) -> bool:
        """Memastikan profil UMKM tersedia."""
        ...

    def is_active_category(self, category_id: str) -> bool:
        """Memastikan kategori project tersedia dan aktif."""
        ...

    def get_existing_skill_ids(
        self,
        skill_ids: list[str],
    ) -> set[str]:
        """Mengembalikan ID skill yang ditemukan di database."""
        ...


    # PROJECT SKILLS

    def add_skills(
        self,
        project_id: str,
        skill_ids: list[str],
    ) -> None:
        """Menyimpan relasi project dengan skill."""
        ...