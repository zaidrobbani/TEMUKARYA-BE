from typing import Protocol

from app.modules.discovery.domain.entities import (
    FreelancerDetail,
    FreelancerSearchFilters,
    FreelancerSummary,
)


# ============================================================
# DISCOVERY REPOSITORY CONTRACT
# ============================================================

class DiscoveryRepository(Protocol):
    """
    Kontrak akses data Freelancer.

    Domain Layer tidak mengetahui:
    - SQLAlchemy
    - MySQL
    - FastAPI

    Implementasi query akan dibuat pada
    Infrastructure Layer.
    """

    # ========================================================
    # 1. SEARCH FREELANCERS
    # ========================================================

    def search_freelancers(
        self,
        filters: FreelancerSearchFilters,
        limit: int,
        offset: int,
    ) -> list[FreelancerSummary]:
        """
        Mencari Freelancer berdasarkan filter.

        Mendukung:
        - Nama
        - Profesi
        - Skills
        - Kota
        - Ketersediaan
        - Harga jasa
        - Pengalaman
        - Rating

        Hasil wajib:
        - Tidak memiliki duplikasi Freelancer
        - Memiliki urutan deterministik
        - Menggunakan pagination
        - Tidak membocorkan data autentikasi
        """
        ...

    # ========================================================
    # 2. GET FREELANCER DETAIL
    # ========================================================

    def get_freelancer_detail(
        self,
        freelancer_id: str,
    ) -> FreelancerDetail | None:
        """
        Mengambil informasi publik Freelancer.

        Mengembalikan None jika profil
        Freelancer tidak ditemukan.

        Informasi detail mencakup:
        - Profesional profile
        - Skills
        - Experiences
        - Portfolios
        - Rating dan reviews
        """
        ...