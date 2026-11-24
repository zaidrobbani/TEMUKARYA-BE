import re

from app.modules.admin_statistics.domain.entities import (
    AdminActor,
    AdminSystemStatistics,
)


# ============================================================
# 1. DOMAIN CONSTANTS
# ============================================================

ALLOWED_USER_FILTER_ROLES = frozenset({
    "umkm",
    "freelancer",
})

MAX_PAGE_SIZE = 100
MAX_OFFSET = 10000
MAX_SEARCH_LENGTH = 100
MAX_IDENTIFIER_LENGTH = 36


# ============================================================
# 2. VALIDATE IDENTIFIER
# ============================================================

def validate_identifier(
    value: str,
    field_name: str = "ID",
) -> str:
    """
    Validasi dasar identifier.

    Tidak mengakses database.

    SQL tetap harus menggunakan parameter
    binding di Infrastructure Layer.
    """

    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} harus berupa string"
        )

    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} tidak boleh kosong"
        )

    if len(normalized) > MAX_IDENTIFIER_LENGTH:
        raise ValueError(
            f"{field_name} terlalu panjang"
        )

    invalid_characters = (
        "\x00",
        "/",
        "\\",
    )

    if any(
        char in normalized
        for char in invalid_characters
    ):
        raise ValueError(
            f"{field_name} tidak valid"
        )

    return normalized


# ============================================================
# 3. REQUIRE ADMIN ACTOR
# ============================================================

def require_admin_actor(
    actor: AdminActor,
) -> None:
    """
    Hanya pengguna dengan role Admin yang
    dapat menggunakan modul ini.

    Actor wajib berasal dari JWT terverifikasi.
    """

    if not isinstance(actor, AdminActor):
        raise PermissionError(
            "Identitas Admin tidak valid"
        )

    try:
        normalized_id = validate_identifier(
            actor.user_id,
            "Admin ID",
        )
    except ValueError as exc:
        raise PermissionError(
            "Identitas Admin tidak valid"
        ) from exc

    if normalized_id != actor.user_id:
        raise PermissionError(
            "Identitas Admin tidak valid"
        )

    if not isinstance(actor.role, str):
        raise PermissionError(
            "Role pengguna tidak valid"
        )

    if actor.role.strip().lower() != "admin":
        raise PermissionError(
            "Akses hanya diperbolehkan untuk Admin"
        )


# ============================================================
# 4. VALIDATE PAGINATION
# ============================================================

def validate_pagination(
    limit: int,
    offset: int,
) -> tuple[int, int]:
    """
    Validasi limit dan offset.

    Limit:
        1 sampai 100

    Offset:
        0 sampai 10000
    """

    if (
        type(limit) is not int
        or limit < 1
        or limit > MAX_PAGE_SIZE
    ):
        raise ValueError(
            "Limit harus antara 1 dan 100"
        )

    if (
        type(offset) is not int
        or offset < 0
        or offset > MAX_OFFSET
    ):
        raise ValueError(
            "Offset harus antara 0 dan 10000"
        )

    return limit, offset


# ============================================================
# 5. NORMALIZE SEARCH QUERY
# ============================================================

def normalize_search_query(
    query: str | None,
) -> str | None:
    """
    Normalisasi kata pencarian.

    Contoh:
        "  desain logo  "
        menjadi:
        "desain logo"

    Escaping karakter LIKE dilakukan
    oleh Infrastructure Layer.
    """

    if query is None:
        return None

    if not isinstance(query, str):
        raise ValueError(
            "Query pencarian harus berupa string"
        )

    normalized = query.strip()

    if not normalized:
        return None

    if len(normalized) > MAX_SEARCH_LENGTH:
        raise ValueError(
            "Query pencarian terlalu panjang"
        )

    if "\x00" in normalized:
        raise ValueError(
            "Query pencarian tidak valid"
        )

    return normalized


# ============================================================
# 6. NORMALIZE USER ROLE FILTER
# ============================================================

def normalize_user_role_filter(
    role: str | None,
) -> str | None:
    """
    Filter role untuk daftar pengguna.

    Role yang boleh digunakan:
        umkm
        freelancer

    None berarti tanpa filter.
    """

    if role is None:
        return None

    if not isinstance(role, str):
        raise ValueError(
            "Role filter harus berupa string"
        )

    normalized = role.strip().lower()

    if not normalized:
        return None

    if normalized not in ALLOWED_USER_FILTER_ROLES:
        raise ValueError(
            "Filter role hanya UMKM atau Freelancer"
        )

    return normalized


# ============================================================
# 7. NORMALIZE PROJECT STATUS FILTER
# ============================================================

def normalize_project_status_filter(
    status: str | None,
) -> str | None:
    """
    Normalisasi filter status Project.

    Tidak membatasi daftar status secara tetap
    karena status Project diatur oleh Workflow.

    Contoh:
        " selesai "
        menjadi:
        "SELESAI"
    """

    if status is None:
        return None

    if not isinstance(status, str):
        raise ValueError(
            "Status Project harus berupa string"
        )

    normalized = status.strip().upper()

    if not normalized:
        return None

    if not re.fullmatch(
        r"[A-Z0-9_]{1,40}",
        normalized,
    ):
        raise ValueError(
            "Format status Project tidak valid"
        )

    return normalized


# ============================================================
# 8. VALIDATE NON-NEGATIVE INTEGER
# ============================================================

def validate_non_negative_integer(
    value: int,
    field_name: str,
) -> int:
    """
    Statistik tidak boleh bernilai negatif.

    bool juga harus ditolak karena:
        isinstance(True, int) == True
    """

    if type(value) is not int:
        raise ValueError(
            f"{field_name} harus berupa integer"
        )

    if value < 0:
        raise ValueError(
            f"{field_name} tidak boleh negatif"
        )

    return value


# ============================================================
# 9. BUILD SYSTEM STATISTICS
# ============================================================

def build_system_statistics(
    *,
    total_umkm: int,
    total_freelancers: int,
    total_projects: int,
    completed_projects: int,
    total_transactions: int,
    platform_income: int,
) -> AdminSystemStatistics:
    """
    Membangun hasil statistik sistem.

    Semua angka harus integer non-negatif.

    Project selesai tidak mungkin lebih
    banyak dari total seluruh Project.
    """

    values = {
        "total_umkm": total_umkm,
        "total_freelancers": total_freelancers,
        "total_projects": total_projects,
        "completed_projects": completed_projects,
        "total_transactions": total_transactions,
        "platform_income": platform_income,
    }

    for field_name, value in values.items():
        validate_non_negative_integer(
            value,
            field_name,
        )

    if completed_projects > total_projects:
        raise ValueError(
            "Jumlah project selesai melebihi "
            "jumlah seluruh project"
        )

    return AdminSystemStatistics(
        total_umkm=total_umkm,
        total_freelancers=total_freelancers,
        total_projects=total_projects,
        completed_projects=completed_projects,
        total_transactions=total_transactions,
        platform_income=platform_income,
    )