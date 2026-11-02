from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError

from app.modules.milestones.domain.entities import (
    Milestone,
    MilestoneStatus,
)

from app.modules.milestones.domain.repositories import (
    ProjectMilestoneContext,
)


# ============================================================
# HELPER: DATE CONVERSION
# ============================================================

def _parse_date(
    value: date | str,
) -> date:
    """
    MySQL biasanya mengembalikan date.
    SQLite test dapat mengembalikan string.
    """

    if isinstance(value, date):
        return value

    return date.fromisoformat(value)


# ============================================================
# HELPER: DATETIME CONVERSION
# ============================================================

def _parse_datetime(
    value: datetime | str | None,
) -> datetime | None:

    if value is None or isinstance(
        value,
        datetime,
    ):
        return value

    return datetime.fromisoformat(value)


# ============================================================
# SQLALCHEMY MILESTONE REPOSITORY
# ============================================================

class SqlAlchemyMilestoneRepository:
    """
    Implementasi MilestoneRepository.

    Mengakses tabel:
    - projects
    - project_milestones

    Integrasi peserta Freelancer menunggu
    kontrak Workflow milik Zaid.
    """

    def __init__(
        self,
        session: Session,
    ):
        self._session = session

    # ========================================================
    # 1. GET PROJECT CONTEXT
    # ========================================================

    def get_project_context(
        self,
        project_id: str,
    ) -> ProjectMilestoneContext | None:
        """
        Mengambil informasi project.

        Dipakai untuk:
        - Pemeriksaan kepemilikan UMKM
        - Status project
        - Tanggal mulai dan deadline

        Freelancer access sementara fail-closed.
        """

        statement = text("""
            SELECT
                id,
                umkm_id,
                status,
                started_at,
                deadline

            FROM projects

            WHERE id = :project_id
        """)

        row = self._session.execute(
            statement,
            {
                "project_id": project_id,
            },
        ).mappings().one_or_none()

        if row is None:
            return None

        return ProjectMilestoneContext(
            project_id=str(row["id"]),
            umkm_id=str(row["umkm_id"]),
            status=str(row["status"]),
            started_at=_parse_datetime(
                row["started_at"]
            ),
            deadline=_parse_date(
                row["deadline"]
            ),

            # Belum mempercayai status agreement
            # sebelum kontrak Workflow tersedia.
            freelancer_id=None,
        )

    # ========================================================
    # 2. LIST PROJECT MILESTONES
    # ========================================================

    def list_milestones(
        self,
        project_id: str,
    ) -> tuple[Milestone, ...]:
        """
        Membaca milestone milik satu project.

        Diurutkan menurut sort_order.
        """

        statement = text("""
            SELECT
                id,
                project_id,
                name,
                description,
                weight_percent,
                status,
                sort_order,
                completed_at,
                updated_by_user_id

            FROM project_milestones

            WHERE project_id = :project_id

            ORDER BY
                sort_order ASC,
                id ASC
        """)

        rows = self._session.execute(
            statement,
            {
                "project_id": project_id,
            },
        ).mappings().all()

        return tuple(
            Milestone(
                id=str(row["id"]),
                project_id=str(row["project_id"]),
                name=row["name"],
                description=row["description"],
                weight_percent=Decimal(
                    str(row["weight_percent"])
                ),
                status=MilestoneStatus(
                    row["status"]
                ),
                sort_order=int(
                    row["sort_order"]
                ),
                completed_at=_parse_datetime(
                    row["completed_at"]
                ),
                updated_by_user_id=(
                    str(row["updated_by_user_id"])
                    if row["updated_by_user_id"] is not None
                    else None
                ),
            )
            for row in rows
        )

    # ========================================================
    # 3. GET TOTAL WEIGHT
    # ========================================================

    def get_total_weight(
        self,
        project_id: str,
    ) -> Decimal:
        """
        Menghitung total bobot milestone.

        Fungsi ini menjadi kontrak yang
        dibutuhkan Workflow Zaid.

        Contoh:
        20.00 + 30.00 + 50.00 = 100.00
        """

        statement = text("""
            SELECT weight_percent

            FROM project_milestones

            WHERE project_id = :project_id
        """)

        rows = self._session.execute(
            statement,
            {
                "project_id": project_id,
            },
        ).scalars().all()

        return sum(
            (
                Decimal(str(weight))
                for weight in rows
            ),
            Decimal("0.00"),
        )

    # ========================================================
    # 4. REPLACE PLAN AND RESET APPROVALS
    # ========================================================

    def replace_plan_and_reset_approvals(
        self,
        project_id: str,
        milestones: tuple[Milestone, ...],
    ) -> None:
        """
        WAJIB fail-closed sampai kontrak
        Workflow approval-reset tersedia.

        Penggantian plan dan reset approval
        nantinya harus atomik.
        """

        raise ConflictError(
            "Workflow approval-reset belum "
            "terintegrasi; perubahan rencana ditolak"
        )

    # ========================================================
    # 5. COMPLETE MILESTONE IF PENDING
    # ========================================================

    def complete_if_pending(
        self,
        project_id: str,
        milestone_id: str,
        updated_by_user_id: str,
        completed_at: datetime,
    ) -> bool:
        """
        Menyelesaikan milestone secara kondisional.

        Hanya mengubah milestone dengan:
        status = BELUM_SELESAI

        True:
            Satu milestone berhasil di-update.

        False:
            Tidak ada milestone yang di-update.

        Pemeriksaan izin Workflow dan transaksi
        commit/rollback menjadi tanggung jawab
        Application + Unit of Work.
        """

        # ====================================================
        # 1. NORMALIZE DATETIME TO UTC
        # ====================================================

        if completed_at.tzinfo is not None:
            completed_at = (
                completed_at
                .astimezone(timezone.utc)
                .replace(tzinfo=None)
            )

        # ====================================================
        # 2. CONDITIONAL UPDATE
        # ====================================================

        statement = text("""
            UPDATE project_milestones

            SET
                status = 'SELESAI',
                completed_at = :completed_at,
                updated_by_user_id = :updated_by_user_id

            WHERE project_id = :project_id

              AND id = :milestone_id

              AND status = 'BELUM_SELESAI'
        """)

        result = self._session.execute(
            statement,
            {
                "completed_at": completed_at,
                "updated_by_user_id": (
                    updated_by_user_id
                ),
                "project_id": project_id,
                "milestone_id": milestone_id,
            },
        )

        # ====================================================
        # 3. RETURN UPDATE RESULT
        # ====================================================

        return result.rowcount == 1