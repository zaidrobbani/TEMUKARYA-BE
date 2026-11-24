
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)

from app.modules.matching.application.dto import (
    FreelancerRecommendationsPage,
    ProjectRecommendationsPage,
    RecommendFreelancersInput,
    RecommendProjectsInput,
)

from app.modules.matching.domain.entities import (
    FreelancerRecommendation,
    ProjectRecommendation,
)

from app.modules.matching.domain.repositories import (
    MatchingRepository,
)

from app.modules.matching.domain.scoring import (
    calculate_skill_match,
)


# ============================================================
# BUSINESS CONSTANTS
# ============================================================

MAX_LIMIT = 100
MAX_OFFSET = 10000
MAX_ID_LENGTH = 36


# ============================================================
# SHARED INPUT VALIDATION
# ============================================================

def _normalize_id(
    value: str,
    name: str,
) -> str:
    """
    Membersihkan dan memvalidasi ID.

    UUID menggunakan panjang maksimum 36.
    Validasi format UUID lebih ketat dapat
    ditambahkan di Presentation Layer.
    """

    if not isinstance(value, str):
        raise BadRequestError(
            f"{name} harus berupa string"
        )

    normalized = value.strip()

    if (
        not normalized
        or len(normalized) > MAX_ID_LENGTH
    ):
        raise BadRequestError(
            f"{name} tidak valid"
        )

    return normalized


def _validate_pagination(
    limit: int,
    offset: int,
) -> None:
    """
    Validasi jumlah data dan posisi pagination.
    """

    if (
        type(limit) is not int
        or not 1 <= limit <= MAX_LIMIT
    ):
        raise BadRequestError(
            "Limit harus antara 1 dan 100"
        )

    if (
        type(offset) is not int
        or not 0 <= offset <= MAX_OFFSET
    ):
        raise BadRequestError(
            "Offset harus antara 0 dan 10000"
        )


# ============================================================
# 1. RECOMMEND FREELANCERS FOR PROJECT
# ============================================================

class RecommendFreelancersForProject:
    """
    Use Case rekomendasi Freelancer kepada UMKM.

    Alur:
    1. Validasi input.
    2. Ambil project.
    3. Verifikasi kepemilikan UMKM.
    4. Periksa status project.
    5. Ambil kandidat Freelancer AVAILABLE.
    6. Hitung skor matching.
    7. Terapkan threshold 60%.
    8. Urutkan rekomendasi.
    9. Terapkan pagination.
    """

    def __init__(
        self,
        repository: MatchingRepository,
    ):
        self._repository = repository

    def execute(
        self,
        data: RecommendFreelancersInput,
    ) -> FreelancerRecommendationsPage:

        # ====================================================
        # 1. VALIDATE INPUT
        # ====================================================

        _validate_pagination(
            data.limit,
            data.offset,
        )

        project_id = _normalize_id(
            data.project_id,
            "Project ID",
        )

        umkm_id = _normalize_id(
            data.umkm_id,
            "UMKM ID",
        )

        # ====================================================
        # 2. GET PROJECT
        # ====================================================

        project = self._repository.get_project(
            project_id
        )

        # ====================================================
        # 3. VERIFY PROJECT OWNERSHIP
        # ====================================================

        # Jika project tidak ditemukan ATAU
        # bukan milik UMKM yang meminta,
        # gunakan error sama.
        #
        # Tujuannya agar UMKM lain tidak dapat
        # mengetahui keberadaan project privat.

        if (
            project is None
            or project.umkm_id != umkm_id
        ):
            raise NotFoundError(
                "Project tidak ditemukan"
            )

        # ====================================================
        # 4. VERIFY PROJECT STATUS
        # ====================================================

        if project.status != "TERBUKA":
            raise ConflictError(
                "Rekomendasi hanya tersedia "
                "untuk project TERBUKA"
            )

        # ====================================================
        # 5. PREPARE RECOMMENDATION COLLECTION
        # ====================================================

        matches: list[
            FreelancerRecommendation
        ] = []

        seen: set[str] = set()

        # ====================================================
        # 6. CALCULATE MATCHING
        # ====================================================

        # Project tanpa skill wajib tidak
        # mempunyai dasar perhitungan matching.

        if project.required_skill_ids:

            candidates = (
                self._repository
                .iter_available_freelancers()
            )

            for freelancer in candidates:

                # Hindari kandidat duplikat
                if freelancer.freelancer_id in seen:
                    continue

                seen.add(
                    freelancer.freelancer_id
                )

                # Defense-in-depth:
                # Repository seharusnya hanya
                # mengambil Freelancer AVAILABLE.
                if (
                    freelancer.availability_status
                    != "AVAILABLE"
                ):
                    continue

                # Hitung skor kecocokan skill
                match = calculate_skill_match(
                    project.required_skill_ids,
                    freelancer.skill_ids,
                )

                # Hanya terima >= 60%
                if match.meets_threshold:

                    matches.append(
                        FreelancerRecommendation(
                            freelancer=freelancer,
                            match=match,
                        )
                    )

        # ====================================================
        # 7. SORT RECOMMENDATIONS
        # ====================================================

        # Prioritas sorting:
        # 1. Skor tertinggi
        # 2. Jumlah skill cocok terbanyak
        # 3. Nama Freelancer (A-Z)
        # 4. ID Freelancer (tie-break final)

        matches.sort(
            key=lambda item: (
                -item.match.score_percent,
                -item.match.matched_count,
                item.freelancer.name.casefold(),
                item.freelancer.freelancer_id,
            )
        )

        # ====================================================
        # 8. PAGINATION
        # ====================================================

        page = matches[
            data.offset:
            data.offset + data.limit
        ]

        # ====================================================
        # 9. RETURN RESULT
        # ====================================================

        return FreelancerRecommendationsPage(
            project_id=project_id,
            items=tuple(page),
            limit=data.limit,
            offset=data.offset,
            has_more=(
                len(matches)
                > data.offset + data.limit
            ),
        )


# ============================================================
# 2. RECOMMEND PROJECTS FOR FREELANCER
# ============================================================

class RecommendProjectsForFreelancer:
    """
    Use Case rekomendasi Project kepada Freelancer.

    Alur:
    1. Validasi input.
    2. Ambil profil Freelancer.
    3. Ambil kandidat project TERBUKA.
    4. Hitung kecocokan skill.
    5. Terapkan threshold 60%.
    6. Urutkan rekomendasi.
    7. Terapkan pagination.
    """

    def __init__(
        self,
        repository: MatchingRepository,
    ):
        self._repository = repository

    def execute(
        self,
        data: RecommendProjectsInput,
    ) -> ProjectRecommendationsPage:

        # ====================================================
        # 1. VALIDATE INPUT
        # ====================================================

        _validate_pagination(
            data.limit,
            data.offset,
        )

        freelancer_id = _normalize_id(
            data.freelancer_id,
            "Freelancer ID",
        )

        # ====================================================
        # 2. GET FREELANCER PROFILE
        # ====================================================

        freelancer = (
            self._repository.get_freelancer(
                freelancer_id
            )
        )

        if freelancer is None:
            raise NotFoundError(
                "Profil Freelancer tidak ditemukan"
            )

        # ====================================================
        # 3. PREPARE RECOMMENDATION COLLECTION
        # ====================================================

        matches: list[
            ProjectRecommendation
        ] = []

        seen: set[str] = set()

        # ====================================================
        # 4. CALCULATE MATCHING
        # ====================================================

        # Freelancer tanpa skill belum bisa
        # menerima rekomendasi berbasis skill.

        if freelancer.skill_ids:

            candidates = (
                self._repository
                .iter_published_projects()
            )

            for project in candidates:

                # Hindari duplikasi Project
                if project.project_id in seen:
                    continue

                seen.add(
                    project.project_id
                )

                # Hanya project TERBUKA
                if project.status != "TERBUKA":
                    continue

                # Project tanpa skill wajib
                # tidak dapat dihitung skornya.
                if not project.required_skill_ids:
                    continue

                # Hitung skor kecocokan
                match = calculate_skill_match(
                    project.required_skill_ids,
                    freelancer.skill_ids,
                )

                # Hanya terima >= 60%
                if match.meets_threshold:

                    matches.append(
                        ProjectRecommendation(
                            project=project,
                            match=match,
                        )
                    )

        # ====================================================
        # 5. SORT RECOMMENDATIONS
        # ====================================================

        # Prioritas sorting:
        # 1. Skor tertinggi
        # 2. Jumlah skill cocok terbanyak
        # 3. Judul Project (A-Z)
        # 4. ID Project

        matches.sort(
            key=lambda item: (
                -item.match.score_percent,
                -item.match.matched_count,
                item.project.title.casefold(),
                item.project.project_id,
            )
        )

        # ====================================================
        # 6. PAGINATION
        # ====================================================

        page = matches[
            data.offset:
            data.offset + data.limit
        ]

        # ====================================================
        # 7. RETURN RESULT
        # ====================================================

        return ProjectRecommendationsPage(
            freelancer_id=freelancer_id,
            items=tuple(page),
            limit=data.limit,
            offset=data.offset,
            has_more=(
                len(matches)
                > data.offset + data.limit
            ),
        )