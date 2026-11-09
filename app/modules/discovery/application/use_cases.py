
import math

from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
)

from app.modules.discovery.application.dto import (
    FreelancersPage,
    SearchFreelancersInput,
)

from app.modules.discovery.domain.entities import (
    FreelancerDetail,
    FreelancerSearchFilters,
)

from app.modules.discovery.domain.repositories import (
    DiscoveryRepository,
)


# ============================================================
# BUSINESS CONSTANTS
# ============================================================

MAX_SEARCH_LENGTH = 100
MAX_CITY_LENGTH = 100
MAX_AVAILABILITY_LENGTH = 25

MAX_SKILL_ID_LENGTH = 50
MAX_SKILL_FILTERS = 50

MAX_PAGE_LIMIT = 100
MAX_PAGE_OFFSET = 10000

MAX_SERVICE_PRICE = (2**64) - 1


# ============================================================
# SHARED VALIDATION HELPERS
# ============================================================

def normalize_optional_text(
    value: str | None,
    field_name: str,
    max_length: int,
) -> str | None:
    """
    Memvalidasi teks opsional dan menghapus
    spasi di awal serta akhir.
    """

    if value is None:
        return None

    if not isinstance(value, str):
        raise BadRequestError(
            f"{field_name} harus berupa teks"
        )

    normalized = value.strip()

    if not normalized:
        raise BadRequestError(
            f"{field_name} tidak boleh kosong"
        )

    if len(normalized) > max_length:
        raise BadRequestError(
            f"{field_name} maksimal {max_length} karakter"
        )

    return normalized


def validate_optional_price(
    value: int | None,
    field_name: str,
) -> None:
    """
    Harga jasa memakai BIGINT UNSIGNED
    pada database MySQL.
    """

    if value is None:
        return

    if (
        type(value) is not int
        or not 0 <= value <= MAX_SERVICE_PRICE
    ):
        raise BadRequestError(
            f"{field_name} harus berupa bilangan "
            "bulat tidak negatif yang valid"
        )


def validate_pagination(
    limit: int,
    offset: int,
) -> None:

    if (
        type(limit) is not int
        or not 1 <= limit <= MAX_PAGE_LIMIT
    ):
        raise BadRequestError(
            "Limit harus berupa bilangan bulat "
            "antara 1 dan 100"
        )

    if (
        type(offset) is not int
        or not 0 <= offset <= MAX_PAGE_OFFSET
    ):
        raise BadRequestError(
            "Offset harus berupa bilangan bulat "
            "antara 0 dan 10000"
        )


def normalize_skill_ids(
    skill_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """
    Menghapus duplikasi skill tanpa mengubah
    urutan filter yang dikirim.
    """

    if not isinstance(skill_ids, tuple):
        raise BadRequestError(
            "Skill IDs harus berupa tuple"
        )

    if len(skill_ids) > MAX_SKILL_FILTERS:
        raise BadRequestError(
            "Terlalu banyak filter skill"
        )

    normalized = []
    seen = set()

    for skill_id in skill_ids:

        valid_id = normalize_optional_text(
            skill_id,
            "Skill ID",
            MAX_SKILL_ID_LENGTH,
        )

        if valid_id not in seen:
            normalized.append(valid_id)
            seen.add(valid_id)

    return tuple(normalized)


# ============================================================
# 1. SEARCH FREELANCERS
# ============================================================

class SearchFreelancers:
    """
    Use Case pencarian Freelancer oleh UMKM.

    Tanggung jawab:
    - Validasi input
    - Normalisasi filter
    - Pagination
    - Memanggil Repository

    Query SQL tidak ditulis pada layer ini.
    """

    def __init__(
        self,
        repository: DiscoveryRepository,
    ):
        self._repository = repository

    def execute(
        self,
        data: SearchFreelancersInput,
    ) -> FreelancersPage:

        # ====================================================
        # 1. VALIDASI PAGINATION
        # ====================================================

        validate_pagination(
            limit=data.limit,
            offset=data.offset,
        )

        # ====================================================
        # 2. NORMALISASI SEARCH & TEXT FILTERS
        # ====================================================

        search = normalize_optional_text(
            data.search,
            "Search",
            MAX_SEARCH_LENGTH,
        )

        city = normalize_optional_text(
            data.city,
            "City",
            MAX_CITY_LENGTH,
        )

        availability = normalize_optional_text(
            data.availability_status,
            "Availability status",
            MAX_AVAILABILITY_LENGTH,
        )

        # ====================================================
        # 3. VALIDASI SKILLS
        # ====================================================

        skill_ids = normalize_skill_ids(
            data.skill_ids
        )

        # ====================================================
        # 4. VALIDASI PRICE RANGE
        # ====================================================

        validate_optional_price(
            data.min_price,
            "Min price",
        )

        validate_optional_price(
            data.max_price,
            "Max price",
        )

        if (
            data.min_price is not None
            and data.max_price is not None
            and data.min_price > data.max_price
        ):
            raise BadRequestError(
                "Min price tidak boleh melebihi max price"
            )

        # ====================================================
        # 5. VALIDASI EXPERIENCE COUNT
        # ====================================================

        if data.min_experience_count is not None:

            if (
                type(data.min_experience_count) is not int
                or data.min_experience_count < 0
            ):
                raise BadRequestError(
                    "Minimum experience count harus "
                    "berupa bilangan bulat tidak negatif"
                )

        # ====================================================
        # 6. VALIDASI RATING
        # ====================================================

        if data.min_rating is not None:

            if (
                type(data.min_rating) not in (int, float)
                or not math.isfinite(data.min_rating)
                or not 0 <= data.min_rating <= 5
            ):
                raise BadRequestError(
                    "Minimum rating harus berupa "
                    "angka antara 0 dan 5"
                )

        # ====================================================
        # 7. BUILD DOMAIN FILTERS
        # ====================================================

        filters = FreelancerSearchFilters(
            search=search,
            skill_ids=skill_ids,
            city=city,
            availability_status=availability,
            min_price=data.min_price,
            max_price=data.max_price,
            min_experience_count=(
                data.min_experience_count
            ),
            min_rating=data.min_rating,
        )

        # ====================================================
        # 8. EXECUTE REPOSITORY QUERY
        # ====================================================

        # Ambil satu data tambahan agar kita tahu
        # apakah halaman berikutnya masih tersedia.
        freelancers = self._repository.search_freelancers(
            filters=filters,
            limit=data.limit + 1,
            offset=data.offset,
        )

        # ====================================================
        # 9. BUILD PAGINATED RESULT
        # ====================================================

        return FreelancersPage(
            items=tuple(freelancers[:data.limit]),
            limit=data.limit,
            offset=data.offset,
            has_more=len(freelancers) > data.limit,
        )


# ============================================================
# 2. GET FREELANCER DETAIL
# ============================================================

class GetFreelancerDetail:
    """
    Use Case mengambil profil detail Freelancer.

    Repository hanya boleh mengembalikan
    informasi publik sesuai Domain Entity.
    """

    def __init__(
        self,
        repository: DiscoveryRepository,
    ):
        self._repository = repository

    def execute(
        self,
        freelancer_id: str,
    ) -> FreelancerDetail:

        # ====================================================
        # 1. VALIDASI FREELANCER ID
        # ====================================================

        if not isinstance(freelancer_id, str):
            raise BadRequestError(
                "Freelancer ID harus berupa teks"
            )

        freelancer_id = freelancer_id.strip()

        if not freelancer_id:
            raise BadRequestError(
                "Freelancer ID tidak boleh kosong"
            )

        if len(freelancer_id) > 36:
            raise BadRequestError(
                "Freelancer ID terlalu panjang"
            )

        # ====================================================
        # 2. GET DETAIL FROM REPOSITORY
        # ====================================================

        freelancer = (
            self._repository.get_freelancer_detail(
                freelancer_id=freelancer_id,
            )
        )

        # ====================================================
        # 3. HANDLE NOT FOUND
        # ====================================================

        if freelancer is None:
            raise NotFoundError(
                "Profil Freelancer tidak ditemukan"
            )

        return freelancer