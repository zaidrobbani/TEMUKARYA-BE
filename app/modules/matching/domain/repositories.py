
from collections.abc import Iterable
from typing import Protocol

from app.modules.matching.domain.entities import (
    FreelancerMatchingSource,
    ProjectMatchingSource,
)


# ============================================================
# MATCHING REPOSITORY CONTRACT
# ============================================================

class MatchingRepository(Protocol):
    """
    Kontrak untuk membaca data Matching.

    Domain Layer tidak mengetahui:
    - MySQL
    - SQLAlchemy
    - FastAPI

    Implementasi database akan dibuat
    pada Infrastructure Layer.
    """

    # ========================================================
    # 1. GET PROJECT
    # ========================================================

    def get_project(
        self,
        project_id: str,
    ) -> ProjectMatchingSource | None:
        """
        Mengambil project beserta skill wajibnya.

        Mengembalikan None jika tidak ditemukan.
        """
        ...

    # ========================================================
    # 2. GET FREELANCER
    # ========================================================

    def get_freelancer(
        self,
        freelancer_id: str,
    ) -> FreelancerMatchingSource | None:
        """
        Mengambil Freelancer beserta skill-nya.

        Mengembalikan None jika tidak ditemukan.
        """
        ...

    # ========================================================
    # 3. AVAILABLE FREELANCERS
    # ========================================================

    def iter_available_freelancers(
        self,
    ) -> Iterable[FreelancerMatchingSource]:
        """
        Mengambil kandidat Freelancer AVAILABLE.

        Digunakan saat UMKM meminta rekomendasi
        Freelancer untuk suatu project.
        """
        ...

    # ========================================================
    # 4. PUBLISHED PROJECTS
    # ========================================================

    def iter_published_projects(
        self,
    ) -> Iterable[ProjectMatchingSource]:
        """
        Mengambil kandidat project TERBUKA.

        Digunakan saat Freelancer meminta
        rekomendasi project yang relevan.
        """
        ...