
from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from app.core.unit_of_work import UnitOfWork
from app.modules.projects.application.dto import CreateProjectInput
from app.modules.projects.domain.entities import Project
from app.modules.projects.domain.repositories import ProjectRepository

from app.core.exceptions import NotFoundError

from dataclasses import replace

from app.core.exceptions import NotFoundError, ConflictError
from app.modules.projects.application.dto import UpdateProjectInput

from app.modules.projects.application.dto import PublicProjectsPage

class CreateProject:
    """Use case untuk membuat dan memublikasikan proyek UMKM."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        uow: UnitOfWork,
        clock: Callable[[], datetime],
    ):
        self._repository = project_repository
        self._uow = uow
        self._clock = clock

    def execute(
        self,
        umkm_id: str,
        data: CreateProjectInput,
    ) -> Project:

        # 1. Validasi informasi dasar proyek
        title = data.title.strip()
        description = data.description.strip()

        if not title or len(title) > 180:
            raise ValueError("Judul proyek tidak valid.")

        if not description:
            raise ValueError("Deskripsi proyek wajib diisi.")

        if data.budget <= 0:
            raise ValueError("Budget proyek harus lebih dari nol.")

        # 2. Validasi profil UMKM
        if not self._repository.umkm_profile_exists(umkm_id):
            raise ValueError("Profil UMKM tidak ditemukan.")

        # 3. Validasi kategori
        if not self._repository.is_active_category(data.category_id):
            raise ValueError("Kategori proyek tidak valid atau tidak aktif.")

        # 4. Validasi skill
        skill_ids = list(data.skill_ids)

        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("Skill proyek tidak boleh duplikat.")

        existing_skills = self._repository.get_existing_skill_ids(
            skill_ids
        )

        if set(skill_ids) != existing_skills:
            raise ValueError("Terdapat skill yang tidak terdaftar.")

        # 5. Buat entity proyek
        project = Project(
            id=str(uuid4()),
            umkm_id=umkm_id,
            category_id=data.category_id,
            title=title,
            description=description,
            budget=data.budget,
            deadline=data.deadline,
            status="TERBUKA",
            published_at=self._clock(),
        )

        # 6. Simpan proyek dan skill
        saved_project = self._repository.add(project)

        self._repository.add_skills(
            saved_project.id,
            skill_ids,
        )

        # 7. Commit transaksi
        self._uow.commit()

        return saved_project


class GetMyProjects:
    """Use case untuk melihat daftar proyek milik UMKM."""

    def __init__(
        self,
        project_repository: ProjectRepository,
    ):
        self._repository = project_repository

    def execute(self, umkm_id: str) -> list[Project]:
        return self._repository.list_by_umkm_id(umkm_id)



class GetProjectDetail:
    """Mengambil detail proyek dengan pemeriksaan visibilitas."""

    def __init__(
        self,
        project_repository: ProjectRepository,
    ):
        self._repository = project_repository

    def execute(
        self,
        project_id: str,
        requester_id: str,
    ) -> Project:
        project = self._repository.get_by_id(project_id)

        if project is None:
            raise NotFoundError("Proyek tidak ditemukan")

        # Pemilik dapat melihat proyeknya sendiri.
        if project.umkm_id == requester_id:
            return project

        # Pengguna lain hanya dapat melihat proyek publik
        # yang masih terbuka.
        is_public = (
            project.published_at is not None
            and project.status == "TERBUKA"
        )

        if not is_public:
            raise NotFoundError("Proyek tidak ditemukan")

        return project


class UpdateProject:
    """Memperbarui proyek milik UMKM sebelum pengerjaan."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        uow: UnitOfWork,
    ):
        self._repository = project_repository
        self._uow = uow

    def execute(
        self,
        umkm_id: str,
        project_id: str,
        data: UpdateProjectInput,
    ) -> Project:

        # 1. Ambil proyek.
        existing = self._repository.get_by_id(project_id)

        # Pastikan proyek ada dan dimiliki UMKM.
        if existing is None or existing.umkm_id != umkm_id:
            raise NotFoundError("Proyek tidak ditemukan")

        # 2. Pastikan proyek masih dapat diedit.
        if existing.status != "TERBUKA" or existing.started_at is not None:
            raise ConflictError(
                "Proyek yang sudah dimulai tidak dapat diubah"
            )

        # 3. Validasi input.
        title = data.title.strip()
        description = data.description.strip()

        if not title or len(title) > 180:
            raise ValueError(
                "Judul proyek wajib diisi dan maksimal 180 karakter"
            )

        if not description:
            raise ValueError("Deskripsi proyek wajib diisi")

        if data.budget <= 0:
            raise ValueError("Budget harus lebih besar dari nol")

        if not self._repository.is_active_category(data.category_id):
            raise ValueError(
                "Kategori proyek tidak valid atau tidak aktif"
            )

        if len(data.skill_ids) != len(set(data.skill_ids)):
            raise ValueError("Skill proyek tidak boleh duplikat")

        existing_skills = self._repository.get_existing_skill_ids(
            list(data.skill_ids)
        )

        if set(data.skill_ids) != existing_skills:
            raise ValueError("Terdapat skill yang tidak valid")

        # 4. Siapkan entity yang diperbarui.
        updated = replace(
            existing,
            category_id=data.category_id,
            title=title,
            description=description,
            budget=data.budget,
            deadline=data.deadline,
        )

        # 5. Update project dan skill.
        saved = self._repository.update(
            project=updated,
            skill_ids=data.skill_ids,
        )

        if saved is None:
            raise ConflictError(
                "Proyek tidak dapat diperbarui karena kondisinya berubah"
            )

        # 6. Commit transaksi.
        self._uow.commit()

        return saved


class DeleteProject:
    """Menghapus proyek milik UMKM jika masih memenuhi syarat."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        uow: UnitOfWork,
    ):
        self._repository = project_repository
        self._uow = uow

    def execute(
        self,
        umkm_id: str,
        project_id: str,
    ) -> None:

        # 1. Cari proyek.
        project = self._repository.get_by_id(project_id)

        # 2. Verifikasi kepemilikan.
        if project is None or project.umkm_id != umkm_id:
            raise NotFoundError("Proyek tidak ditemukan")

        # 3. Pastikan proyek belum dimulai.
        if (
            project.status != "TERBUKA"
            or project.started_at is not None
        ):
            raise ConflictError(
                "Proyek yang sudah diproses tidak dapat dihapus"
            )

        # 4. Repository memeriksa kembali kondisi
        # proyek dan relasinya saat DELETE dijalankan.
        deleted = self._repository.delete(
            project_id=project_id,
            umkm_id=umkm_id,
        )

        if not deleted:
            raise ConflictError(
                "Proyek tidak dapat dihapus karena memiliki "
                "data terkait atau kondisinya telah berubah"
            )

        # 5. Commit satu transaksi.
        self._uow.commit()


class DeleteProject:
    """Menghapus proyek milik UMKM yang masih memenuhi syarat."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        uow: UnitOfWork,
    ):
        self._repository = project_repository
        self._uow = uow

    def execute(
        self,
        umkm_id: str,
        project_id: str,
    ) -> None:

        project = self._repository.get_by_id(project_id)

        # Jangan mengungkap proyek milik UMKM lain.
        if project is None or project.umkm_id != umkm_id:
            raise NotFoundError("Proyek tidak ditemukan")

        # Proyek harus masih terbuka dan belum dimulai.
        if (
            project.status != "TERBUKA"
            or project.started_at is not None
        ):
            raise ConflictError(
                "Proyek yang sudah diproses tidak dapat dihapus"
            )

        # Repository melakukan pemeriksaan kondisi
        # dan relasi proyek langsung di MySQL.
        deleted = self._repository.delete(
            project_id=project_id,
            umkm_id=umkm_id,
        )

        if not deleted:
            raise ConflictError(
                "Proyek tidak dapat dihapus karena memiliki "
                "data terkait atau kondisinya telah berubah"
            )

        self._uow.commit()


class SearchPublicProjects:
    """Mencari proyek yang tersedia untuk Freelancer."""

    def __init__(
        self,
        project_repository: ProjectRepository,
    ):
        self._repository = project_repository

    def execute(
        self,
        search: str | None = None,
        category_id: str | None = None,
        min_budget: int | None = None,
        max_budget: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> PublicProjectsPage:

        if limit < 1 or limit > 100:
            raise ValueError(
                "Limit harus berada di antara 1 dan 100"
            )

        if offset < 0:
            raise ValueError(
                "Offset tidak boleh negatif"
            )

        if min_budget is not None and min_budget < 0:
            raise ValueError(
                "Minimum budget tidak boleh negatif"
            )

        if max_budget is not None and max_budget < 0:
            raise ValueError(
                "Maksimum budget tidak boleh negatif"
            )

        if (
            min_budget is not None
            and max_budget is not None
            and min_budget > max_budget
        ):
            raise ValueError(
                "Minimum budget tidak boleh melebihi maksimum budget"
            )

        # Ambil satu item tambahan untuk mengetahui
        # apakah masih tersedia halaman berikutnya.
        projects = self._repository.search_public(
            search=search,
            category_id=category_id,
            min_budget=min_budget,
            max_budget=max_budget,
            limit=limit + 1,
            offset=offset,
        )

        return PublicProjectsPage(
            items=tuple(projects[:limit]),
            limit=limit,
            offset=offset,
            has_more=len(projects) > limit,
        )