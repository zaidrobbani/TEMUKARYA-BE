
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.modules.milestones.domain.entities import (
    Milestone,
)


# ============================================================
# PROJECT CONTEXT
# ============================================================

@dataclass(frozen=True, slots=True)
class ProjectMilestoneContext:
    """
    Data proyek yang dibutuhkan Milestones.

    UMKM ID berasal dari Projects.
    Freelancer ID berasal dari kesepakatan
    yang dikelola Workflow.
    """

    project_id: str
    umkm_id: str
    status: str
    started_at: datetime | None
    deadline: date

    freelancer_id: str | None = None


# ============================================================
# MILESTONE REPOSITORY CONTRACT
# ============================================================

class MilestoneRepository(Protocol):
    """
    Kontrak akses data Milestones.

    Belum bergantung pada SQLAlchemy atau MySQL.
    """

    def get_project_context(
        self,
        project_id: str,
    ) -> ProjectMilestoneContext | None:
        ...

    def list_milestones(
        self,
        project_id: str,
    ) -> tuple[Milestone, ...]:
        ...

    def get_total_weight(
        self,
        project_id: str,
    ) -> Decimal:
        """
        Kontrak yang dibutuhkan Workflow Zaid.

        Harus menghasilkan Decimal,
        misalnya Decimal('100.00').
        """
        ...

    def replace_plan_and_reset_approvals(
        self,
        project_id: str,
        milestones: tuple[Milestone, ...],
    ) -> None:
        """
        Mengganti seluruh rencana milestone.

        PENTING:
        Penggantian rencana dan reset persetujuan
        harus berada dalam satu transaksi atomik.

        Implementation baru dibuat setelah
        kontrak Workflow disepakati dengan Zaid.
        """
        ...

    def complete_if_pending(
        self,
        project_id: str,
        milestone_id: str,
        updated_by_user_id: str,
        completed_at: datetime,
    ) -> bool:
        """
        Update milestone secara kondisional.

        True:
          BELUM_SELESAI -> SELESAI berhasil.

        False:
          Tidak ada baris yang berhasil diubah.

        Infrastructure harus menggunakan
        UPDATE kondisional agar aman saat
        tombol selesai diklik bersamaan.
        """
        ...