
from sqlalchemy import (
    bindparam,
    delete,
    func,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.orm import Session

from app.modules.projects.domain.entities import Project
from app.modules.projects.domain.repositories import ProjectRepository
from app.modules.projects.infrastructure.models import (
    ProjectModel,
    ProjectSkillModel,
)


class SqlAlchemyProjectRepository(ProjectRepository):
    """Implementasi ProjectRepository menggunakan SQLAlchemy."""

    def __init__(self, session: Session):
        self._session = session

    # ========================================================
    # PROJECT CRUD
    # ========================================================

    def add(self, project: Project) -> Project:
        """Menyimpan project baru ke database."""

        model = ProjectModel(
            id=project.id,
            umkm_id=project.umkm_id,
            category_id=project.category_id,
            title=project.title,
            description=project.description,
            budget=project.budget,
            deadline=project.deadline,
            status=project.status,
            published_at=project.published_at,
        )

        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)

        return _to_entity(model)

    def get_by_id(self, project_id: str) -> Project | None:
        """Mengambil project berdasarkan UUID."""

        model = self._session.get(
            ProjectModel,
            project_id,
        )

        return _to_entity(model) if model else None

    def list_by_umkm_id(self, umkm_id: str) -> list[Project]:
        """Mengambil daftar project milik UMKM."""

        statement = (
            select(ProjectModel)
            .where(ProjectModel.umkm_id == umkm_id)
            .order_by(
                ProjectModel.created_at.desc(),
                ProjectModel.id.desc(),
            )
        )

        models = self._session.scalars(statement).all()

        return [_to_entity(model) for model in models]

    # ========================================================
    # PUBLIC PROJECT SEARCH
    # ========================================================

    def search_public(
        self,
        search: str | None,
        category_id: str | None,
        min_budget: int | None,
        max_budget: int | None,
        limit: int,
        offset: int,
    ) -> list[Project]:
        """
        Mencari project yang telah dipublikasikan
        dan masih berstatus TERBUKA.

        Mendukung:
        - Pencarian judul dan deskripsi
        - Filter kategori
        - Filter rentang budget
        - Pagination limit dan offset
        """

        # 1. Hanya tampilkan project publik yang terbuka.
        statement = select(ProjectModel).where(
            ProjectModel.status == "TERBUKA",
            ProjectModel.published_at.is_not(None),
        )

        # 2. Pencarian berdasarkan judul atau deskripsi.
        if search:
            keyword = search.strip().lower()

            if keyword:
                statement = statement.where(
                    or_(
                        func.lower(
                            ProjectModel.title
                        ).contains(
                            keyword,
                            autoescape=True,
                        ),
                        func.lower(
                            ProjectModel.description
                        ).contains(
                            keyword,
                            autoescape=True,
                        ),
                    )
                )

        # 3. Filter kategori project.
        if category_id:
            statement = statement.where(
                ProjectModel.category_id == category_id
            )

        # 4. Filter minimum budget.
        if min_budget is not None:
            statement = statement.where(
                ProjectModel.budget >= min_budget
            )

        # 5. Filter maksimum budget.
        if max_budget is not None:
            statement = statement.where(
                ProjectModel.budget <= max_budget
            )

        # 6. Urutkan dari project terbaru.
        statement = (
            statement
            .order_by(
                ProjectModel.published_at.desc(),
                ProjectModel.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        # 7. Jalankan query.
        models = self._session.scalars(statement).all()

        # 8. Konversi SQLAlchemy Model ke Domain Entity.
        return [_to_entity(model) for model in models]

    # ========================================================
    # UPDATE PROJECT
    # ========================================================

    def update(
        self,
        project: Project,
        skill_ids: tuple[str, ...],
    ) -> Project | None:
        """
        Memperbarui metadata dan skills project
        dalam satu transaksi database.
        """

        # 1. Update metadata hanya jika project masih
        # TERBUKA, belum dimulai, dan milik UMKM terkait.
        result = self._session.execute(
            update(ProjectModel)
            .where(
                ProjectModel.id == project.id,
                ProjectModel.umkm_id == project.umkm_id,
                ProjectModel.status == "TERBUKA",
                ProjectModel.started_at.is_(None),
            )
            .values(
                category_id=project.category_id,
                title=project.title,
                description=project.description,
                budget=project.budget,
                deadline=project.deadline,
            )
            .execution_options(synchronize_session=False)
        )

        if result.rowcount == 0:
            return None

        # 2. Hapus relasi skill lama.
        self._session.execute(
            delete(ProjectSkillModel).where(
                ProjectSkillModel.project_id == project.id
            )
        )

        # 3. Tambahkan relasi skill baru.
        for skill_id in skill_ids:
            self._session.add(
                ProjectSkillModel(
                    project_id=project.id,
                    skill_id=skill_id,
                )
            )

        # 4. Sinkronisasi dengan database.
        self._session.flush()
        self._session.expire_all()

        # 5. Ambil project setelah diperbarui.
        return self.get_by_id(project.id)

    # ========================================================
    # DELETE PROJECT
    # ========================================================

    def delete(
        self,
        project_id: str,
        umkm_id: str,
    ) -> bool:
        """
        Menghapus project jika:
        - Dimiliki oleh UMKM yang meminta.
        - Status masih TERBUKA.
        - Project belum dimulai.
        - Tidak memiliki data terkait yang dilindungi.

        Project skills otomatis terhapus melalui
        Foreign Key ON DELETE CASCADE.

        Commit dilakukan oleh UnitOfWork.
        """

        # 1. Daftar tabel yang harus kosong sebelum
        # project boleh dihapus.
        blocker_tables = (
            "project_applications",
            "project_agreements",
            "project_attachments",
            "project_milestones",
            "project_status_history",
            "project_submissions",
            "freelancer_reviews",
        )

        # 2. Susun pemeriksaan NOT EXISTS.
        # Nama tabel berasal dari konstanta internal,
        # bukan dari input pengguna.
        blocker_checks = " AND ".join(
            (
                "NOT EXISTS ("
                f"SELECT 1 FROM {table} "
                "WHERE project_id = :project_id"
                ")"
            )
            for table in blocker_tables
        )

        # 3. Hapus hanya jika seluruh syarat terpenuhi.
        statement = text(
            """
            DELETE FROM projects
            WHERE id = :project_id
              AND umkm_id = :umkm_id
              AND status = 'TERBUKA'
              AND started_at IS NULL
              AND
            """
            + blocker_checks
        )

        result = self._session.execute(
            statement,
            {
                "project_id": project_id,
                "umkm_id": umkm_id,
            },
        )

        # 4. Berhasil menghapus tepat satu project.
        if result.rowcount == 1:
            self._session.expire_all()
            return True

        # Project tidak memenuhi syarat.
        return False

    # ========================================================
    # BUSINESS VALIDATION QUERIES
    # ========================================================

    def umkm_profile_exists(self, umkm_id: str) -> bool:
        """Memastikan UMKM memiliki profil."""

        statement = text(
            "SELECT 1 FROM umkm_profiles "
            "WHERE user_id = :umkm_id LIMIT 1"
        )

        result = self._session.execute(
            statement,
            {"umkm_id": umkm_id},
        ).scalar_one_or_none()

        return result is not None

    def is_active_category(self, category_id: str) -> bool:
        """Memastikan kategori tersedia dan aktif."""

        statement = text(
            "SELECT 1 FROM project_categories "
            "WHERE id = :category_id "
            "AND is_active = 1 LIMIT 1"
        )

        result = self._session.execute(
            statement,
            {"category_id": category_id},
        ).scalar_one_or_none()

        return result is not None

    def get_existing_skill_ids(
        self,
        skill_ids: list[str],
    ) -> set[str]:
        """Mengambil ID skill yang tersedia di database."""

        if not skill_ids:
            return set()

        statement = text(
            "SELECT id FROM skills WHERE id IN :skill_ids"
        ).bindparams(
            bindparam("skill_ids", expanding=True)
        )

        result = self._session.execute(
            statement,
            {"skill_ids": skill_ids},
        )

        return set(result.scalars().all())

    # ========================================================
    # PROJECT SKILLS
    # ========================================================

    def add_skills(
        self,
        project_id: str,
        skill_ids: list[str],
    ) -> None:
        """Menambahkan relasi project dengan skill."""

        for skill_id in skill_ids:
            model = ProjectSkillModel(
                project_id=project_id,
                skill_id=skill_id,
            )

            self._session.add(model)


# ============================================================
# MAPPER: SQLALCHEMY MODEL -> DOMAIN ENTITY
# ============================================================

def _to_entity(model: ProjectModel) -> Project:
    """Mengubah SQLAlchemy Model menjadi Domain Entity."""

    return Project(
        id=model.id,
        umkm_id=model.umkm_id,
        category_id=model.category_id,
        title=model.title,
        description=model.description,
        budget=model.budget,
        deadline=model.deadline,
        status=model.status,
        published_at=model.published_at,
        started_at=model.started_at,
        completed_at=model.completed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )