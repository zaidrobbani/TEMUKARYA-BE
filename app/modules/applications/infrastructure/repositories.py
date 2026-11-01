
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError

from app.modules.applications.domain.entities import (
    ProjectApplication,
)
from app.modules.applications.domain.repositories import (
    ApplicationRepository,
)
from app.modules.applications.infrastructure.models import (
    ProjectApplicationModel,
)


def _is_duplicate_application(exc: IntegrityError) -> bool:
    """
    Kenali pelanggaran unique constraint aplikasi,
    bukan seluruh jenis IntegrityError.
    """

    message = str(exc.orig).lower()

    mysql_error_code = None

    if getattr(exc.orig, "args", None):
        mysql_error_code = exc.orig.args[0]

    if (
        mysql_error_code == 1062
        and "uq_project_applications_project_freelancer" in message
    ):
        return True

    # Dukungan SQLite hanya untuk unit test Repository.
    return (
        "unique constraint failed:" in message
        and "project_applications.project_id" in message
        and "project_applications.freelancer_id" in message
    )


def _to_entity(
    model: ProjectApplicationModel,
) -> ProjectApplication:
    return ProjectApplication(
        id=model.id,
        project_id=model.project_id,
        freelancer_id=model.freelancer_id,
        proposed_price=model.proposed_price,
        estimated_duration_days=model.estimated_duration_days,
        proposal_message=model.proposal_message,
        status=model.status,
        submitted_at=model.submitted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyApplicationRepository(ApplicationRepository):
    """
    Implementasi ApplicationRepository menggunakan
    SQLAlchemy dan database session dari UnitOfWork.

    Repository tidak melakukan commit sendiri.
    """

    def __init__(self, session: Session):
        self._session = session

    # ========================================================
    # FREELANCER PROFILE VALIDATION
    # ========================================================

    def freelancer_profile_exists(
        self,
        freelancer_id: str,
    ) -> bool:
        statement = text(
            "SELECT 1 "
            "FROM freelancer_profiles "
            "WHERE user_id = :freelancer_id "
            "LIMIT 1"
        )

        result = self._session.scalar(
            statement,
            {"freelancer_id": freelancer_id},
        )

        return result is not None

    # ========================================================
    # PROJECT AVAILABILITY
    # ========================================================

    def project_is_open(
        self,
        project_id: str,
        lock: bool = False,
    ) -> bool:
        query = (
            "SELECT id "
            "FROM projects "
            "WHERE id = :project_id "
            "AND status = 'TERBUKA' "
            "AND published_at IS NOT NULL "
            "AND started_at IS NULL "
            "LIMIT 1"
        )

        if lock:
            # Digunakan oleh SubmitApplication
            # ketika transaksi berjalan di MySQL.
            query += " FOR UPDATE"

        result = self._session.scalar(
            text(query),
            {"project_id": project_id},
        )

        return result is not None

    # ========================================================
    # PROJECT OWNERSHIP
    # ========================================================

    def project_owned_by_umkm(
        self,
        project_id: str,
        umkm_id: str,
    ) -> bool:
        statement = text(
            "SELECT 1 "
            "FROM projects "
            "WHERE id = :project_id "
            "AND umkm_id = :umkm_id "
            "LIMIT 1"
        )

        result = self._session.scalar(
            statement,
            {
                "project_id": project_id,
                "umkm_id": umkm_id,
            },
        )

        return result is not None

    # ========================================================
    # CREATE APPLICATION
    # ========================================================

    def add(
        self,
        application: ProjectApplication,
    ) -> ProjectApplication:
        model = ProjectApplicationModel(
            id=application.id,
            project_id=application.project_id,
            freelancer_id=application.freelancer_id,
            proposed_price=application.proposed_price,
            estimated_duration_days=(
                application.estimated_duration_days
            ),
            proposal_message=application.proposal_message,
            status=application.status,
        )

        self._session.add(model)

        try:
            self._session.flush()
            self._session.refresh(model)

        except IntegrityError as exc:
            if _is_duplicate_application(exc):
                raise ConflictError(
                    "Kamu sudah pernah melamar proyek ini"
                ) from exc

            raise

        return _to_entity(model)

    # ========================================================
    # GET APPLICATION BY ID
    # ========================================================

    def get_by_id(
        self,
        application_id: str,
    ) -> ProjectApplication | None:
        model = self._session.get(
            ProjectApplicationModel,
            application_id,
        )

        if model is None:
            return None

        return _to_entity(model)

    # ========================================================
    # GET APPLICATION BY PROJECT AND FREELANCER
    # ========================================================

    def get_by_project_and_freelancer(
        self,
        project_id: str,
        freelancer_id: str,
    ) -> ProjectApplication | None:
        statement = select(
            ProjectApplicationModel
        ).where(
            ProjectApplicationModel.project_id == project_id,
            ProjectApplicationModel.freelancer_id == freelancer_id,
        )

        model = self._session.scalar(statement)

        if model is None:
            return None

        return _to_entity(model)

    # ========================================================
    # LIST FREELANCER APPLICATIONS
    # ========================================================

    def list_by_freelancer(
        self,
        freelancer_id: str,
        limit: int,
        offset: int,
    ) -> list[ProjectApplication]:
        statement = (
            select(ProjectApplicationModel)
            .where(
                ProjectApplicationModel.freelancer_id
                == freelancer_id
            )
            .order_by(
                ProjectApplicationModel.submitted_at.desc(),
                ProjectApplicationModel.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        models = self._session.scalars(statement).all()

        return [_to_entity(model) for model in models]

    # ========================================================
    # LIST PROJECT APPLICANTS
    # ========================================================

    def list_by_project(
        self,
        project_id: str,
        limit: int,
        offset: int,
    ) -> list[ProjectApplication]:
        statement = (
            select(ProjectApplicationModel)
            .where(
                ProjectApplicationModel.project_id == project_id
            )
            .order_by(
                ProjectApplicationModel.submitted_at.desc(),
                ProjectApplicationModel.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        models = self._session.scalars(statement).all()

        return [_to_entity(model) for model in models]