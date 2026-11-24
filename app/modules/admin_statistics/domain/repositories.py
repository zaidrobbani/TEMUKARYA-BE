from typing import Protocol

from app.modules.admin_statistics.domain.entities import (
    AdminProjectDetail,
    AdminProjectSummary,
    AdminSystemStatistics,
    AdminUserDetail,
    AdminUserSummary,
)


# ============================================================
# ADMIN STATISTICS REPOSITORY CONTRACT
# ============================================================

class AdminStatisticsRepository(Protocol):
    """
    Repository contract Admin Statistics.

    Seluruh metode bersifat READ-ONLY.

    Implementasi SQLAlchemy akan dibuat
    pada Infrastructure Layer.
    """

    # ========================================================
    # 1. LIST USERS
    # ========================================================

    def list_users(
        self,
        *,
        role: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[AdminUserSummary, ...]:
        """
        Mengambil daftar pengguna.

        Mendukung:
            Filter role
            Pencarian nama/email
            Pagination
        """
        ...

    # ========================================================
    # 2. COUNT USERS
    # ========================================================

    def count_users(
        self,
        *,
        role: str | None,
        search: str | None,
    ) -> int:
        """
        Menghitung pengguna yang sesuai filter.

        Digunakan untuk metadata pagination.
        """
        ...

    # ========================================================
    # 3. GET USER DETAIL
    # ========================================================

    def get_user_detail(
        self,
        user_id: str,
    ) -> AdminUserDetail | None:
        """
        Mengambil detail pengguna.

        Mengembalikan None jika tidak ditemukan.
        """
        ...

    # ========================================================
    # 4. LIST PROJECTS
    # ========================================================

    def list_projects(
        self,
        *,
        status: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[AdminProjectSummary, ...]:
        """
        Mengambil daftar seluruh Project.

        Mendukung:
            Filter status
            Pencarian judul
            Pagination
        """
        ...

    # ========================================================
    # 5. COUNT PROJECTS
    # ========================================================

    def count_projects(
        self,
        *,
        status: str | None,
        search: str | None,
    ) -> int:
        """
        Menghitung Project sesuai filter.
        """
        ...

    # ========================================================
    # 6. GET PROJECT DETAIL
    # ========================================================

    def get_project_detail(
        self,
        project_id: str,
    ) -> AdminProjectDetail | None:
        """
        Mengambil detail Project.

        Meliputi:
            UMKM pemilik
            Freelancer yang ditugaskan
            Budget
            Nilai kesepakatan
            Status dan tanggal Project
        """
        ...

    # ========================================================
    # 7. GET SYSTEM STATISTICS
    # ========================================================

    def get_system_statistics(
        self,
    ) -> AdminSystemStatistics:
        """
        Mengambil ringkasan statistik sistem.

        Meliputi:
            Jumlah UMKM
            Jumlah Freelancer
            Total Project
            Project selesai
            Jumlah transaksi
            Total income platform
        """
        ...