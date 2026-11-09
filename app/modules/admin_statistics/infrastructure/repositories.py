
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.admin_statistics.domain.entities import (
    AdminFreelancerProfile,
    AdminProjectDetail,
    AdminProjectSummary,
    AdminSystemStatistics,
    AdminUMKMProfile,
    AdminUserDetail,
    AdminUserSummary,
)

from app.modules.admin_statistics.domain.statistics_rules import (
    build_system_statistics,
)


# ============================================================
# 1. DATETIME HELPERS
# ============================================================

def _utc_datetime(
    value: datetime | str | None,
) -> datetime | None:
    """
    Konversi DATETIME database ke datetime UTC-aware.

    Konvensi:
        DATETIME tanpa timezone dianggap UTC.

    Konvensi ini harus disepakati dengan
    modul lain saat integrasi.
    """

    if value is None:
        return None

    if isinstance(value, str):
        value = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _date(
    value: date | datetime | str,
) -> date:
    """
    Konversi kolom DATE dari MySQL atau SQLite.
    """

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return date.fromisoformat(value)


# ============================================================
# 2. SQL LIKE HELPER
# ============================================================

def _like_pattern(
    query: str,
) -> str:
    """
    Menjadikan keyword sebagai pencarian literal.

    Karakter SQL LIKE:
        %
        _

    tidak boleh digunakan sebagai wildcard
    secara tidak sengaja oleh pengguna.

    Menggunakan ! sebagai escape character.
    """

    escaped = (
        query.lower()
        .replace("!", "!!")
        .replace("%", "!%")
        .replace("_", "!_")
    )

    return f"%{escaped}%"


# ============================================================
# 3. USER ROW MAPPER
# ============================================================

def _user_from_row(
    row: Any,
) -> AdminUserSummary:
    """
    Mengubah hasil SQL menjadi Domain Entity.

    Password hash tidak diambil dari database.
    """

    return AdminUserSummary(
        id=str(row["id"]),
        name=row["name"],
        email=row["email"],
        role=row["role"],
        created_at=_utc_datetime(
            row["created_at"]
        ),
    )


# ============================================================
# 4. PROJECT ROW MAPPER
# ============================================================

def _project_from_row(
    row: Any,
) -> AdminProjectSummary:

    return AdminProjectSummary(
        id=str(row["id"]),
        title=row["title"],
        category_id=str(row["category_id"]),
        umkm_id=str(row["umkm_id"]),
        umkm_name=row["umkm_name"],
        assigned_freelancer_id=(
            str(row["assigned_freelancer_id"])
            if row["assigned_freelancer_id"] is not None
            else None
        ),
        assigned_freelancer_name=(
            row["assigned_freelancer_name"]
        ),
        budget=int(row["budget"]),
        deadline=_date(row["deadline"]),
        status=row["status"],
        created_at=_utc_datetime(
            row["created_at"]
        ),
    )


# ============================================================
# 5. SHARED PROJECT SQL
# ============================================================

_PROJECT_SELECT = """
SELECT
    p.id,
    p.title,
    p.category_id,
    p.umkm_id,
    owner.name AS umkm_name,
    agreement.freelancer_id AS assigned_freelancer_id,
    freelancer.name AS assigned_freelancer_name,
    p.budget,
    p.deadline,
    p.status,
    p.created_at
"""


_PROJECT_JOINS = """
FROM projects AS p
LEFT JOIN users AS owner
    ON owner.id = p.umkm_id
LEFT JOIN project_agreements AS agreement
    ON agreement.project_id = p.id
LEFT JOIN users AS freelancer
    ON freelancer.id = agreement.freelancer_id
"""


# ============================================================
# 6. ADMIN STATISTICS SQLALCHEMY REPOSITORY
# ============================================================

class SqlAlchemyAdminStatisticsRepository:
    """
    Implementasi Repository Admin Statistics.

    READ-ONLY:
        Tidak menjalankan INSERT.
        Tidak menjalankan UPDATE.
        Tidak menjalankan DELETE.
        Tidak menjalankan commit().

    Session disediakan oleh dependency FastAPI.
    """

    def __init__(
        self,
        session: Session,
    ):
        self._session = session

    # ========================================================
    # A. BUILD USER FILTER
    # ========================================================

    @staticmethod
    def _user_filter(
        role: str | None,
        search: str | None,
    ) -> tuple[str, dict]:

        conditions = []
        params = {}

        if role is not None:
            conditions.append(
                "LOWER(u.role) = :role"
            )

            params["role"] = role.lower()

        if search is not None:
            conditions.append(
                "("
                "LOWER(u.name) LIKE :pattern ESCAPE '!' "
                "OR LOWER(u.email) LIKE :pattern ESCAPE '!'"
                ")"
            )

            params["pattern"] = _like_pattern(
                search
            )

        where_clause = (
            " WHERE " + " AND ".join(conditions)
            if conditions
            else ""
        )

        return where_clause, params

    # ========================================================
    # B. BUILD PROJECT FILTER
    # ========================================================

    @staticmethod
    def _project_filter(
        status: str | None,
        search: str | None,
    ) -> tuple[str, dict]:

        conditions = []
        params = {}

        if status is not None:
            conditions.append(
                "UPPER(p.status) = :status"
            )

            params["status"] = status.upper()

        if search is not None:
            conditions.append(
                "LOWER(p.title) LIKE :pattern ESCAPE '!'"
            )

            params["pattern"] = _like_pattern(
                search
            )

        where_clause = (
            " WHERE " + " AND ".join(conditions)
            if conditions
            else ""
        )

        return where_clause, params

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
        Daftar pengguna dengan filter,
        search dan pagination.
        """

        where_clause, params = self._user_filter(
            role,
            search,
        )

        statement = text(
            "SELECT "
            "u.id, u.name, u.email, u.role, u.created_at "
            "FROM users AS u "
            + where_clause
            + " ORDER BY u.created_at DESC, u.id DESC "
            "LIMIT :limit OFFSET :offset"
        )

        rows = self._session.execute(
            statement,
            {
                **params,
                "limit": limit,
                "offset": offset,
            },
        ).mappings().all()

        return tuple(
            _user_from_row(row)
            for row in rows
        )

    # ========================================================
    # 2. COUNT USERS
    # ========================================================

    def count_users(
        self,
        *,
        role: str | None,
        search: str | None,
    ) -> int:

        where_clause, params = self._user_filter(
            role,
            search,
        )

        statement = text(
            "SELECT COUNT(*) "
            "FROM users AS u "
            + where_clause
        )

        result = self._session.execute(
            statement,
            params,
        ).scalar_one()

        return int(result)

    # ========================================================
    # 3. GET USER DETAIL
    # ========================================================

    def get_user_detail(
        self,
        user_id: str,
    ) -> AdminUserDetail | None:
        """
        Mengambil informasi User dan profil
        berdasarkan role pengguna.

        Tidak mengambil password_hash.
        """

        # ----------------------------------------------------
        # A. GET BASE USER
        # ----------------------------------------------------

        statement = text(
            "SELECT id, name, email, role, created_at "
            "FROM users "
            "WHERE id = :id"
        )

        row = self._session.execute(
            statement,
            {
                "id": user_id,
            },
        ).mappings().one_or_none()

        if row is None:
            return None

        user = _user_from_row(
            row
        )

        umkm_profile = None
        freelancer_profile = None

        # ----------------------------------------------------
        # B. GET UMKM PROFILE
        # ----------------------------------------------------

        if user.role.lower() == "umkm":

            statement = text(
                "SELECT "
                "business_name, "
                "business_category, "
                "business_address, "
                "city "
                "FROM umkm_profiles "
                "WHERE user_id = :id"
            )

            profile = self._session.execute(
                statement,
                {
                    "id": user_id,
                },
            ).mappings().one_or_none()

            if profile is not None:

                umkm_profile = AdminUMKMProfile(
                    business_name=(
                        profile["business_name"]
                    ),
                    business_category=(
                        profile["business_category"]
                    ),
                    business_address=(
                        profile["business_address"]
                    ),
                    city=profile["city"],
                )

        # ----------------------------------------------------
        # C. GET FREELANCER PROFILE
        # ----------------------------------------------------

        elif user.role.lower() == "freelancer":

            statement = text(
                "SELECT "
                "professional_title, "
                "bio, "
                "city, "
                "service_price_min, "
                "service_price_max, "
                "availability_status "
                "FROM freelancer_profiles "
                "WHERE user_id = :id"
            )

            profile = self._session.execute(
                statement,
                {
                    "id": user_id,
                },
            ).mappings().one_or_none()

            if profile is not None:

                freelancer_profile = AdminFreelancerProfile(
                    professional_title=(
                        profile["professional_title"]
                    ),
                    bio=profile["bio"],
                    city=profile["city"],
                    service_price_min=(
                        int(profile["service_price_min"])
                        if profile["service_price_min"] is not None
                        else None
                    ),
                    service_price_max=(
                        int(profile["service_price_max"])
                        if profile["service_price_max"] is not None
                        else None
                    ),
                    availability_status=(
                        profile["availability_status"]
                    ),
                )

        # ----------------------------------------------------
        # D. BUILD DETAIL
        # ----------------------------------------------------

        return AdminUserDetail(
            user=user,
            umkm_profile=umkm_profile,
            freelancer_profile=freelancer_profile,
        )

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
        Menampilkan seluruh Project.

        LEFT JOIN memastikan Project tanpa
        agreement tetap ditampilkan.
        """

        where_clause, params = self._project_filter(
            status,
            search,
        )

        statement = text(
            _PROJECT_SELECT
            + _PROJECT_JOINS
            + where_clause
            + " ORDER BY p.created_at DESC, p.id DESC "
            "LIMIT :limit OFFSET :offset"
        )

        rows = self._session.execute(
            statement,
            {
                **params,
                "limit": limit,
                "offset": offset,
            },
        ).mappings().all()

        return tuple(
            _project_from_row(row)
            for row in rows
        )

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
        Menghitung Project tanpa JOIN agar
        tidak terjadi penghitungan ganda.
        """

        where_clause, params = self._project_filter(
            status,
            search,
        )

        statement = text(
            "SELECT COUNT(*) "
            "FROM projects AS p "
            + where_clause
        )

        result = self._session.execute(
            statement,
            params,
        ).scalar_one()

        return int(result)

    # ========================================================
    # 6. GET PROJECT DETAIL
    # ========================================================

    def get_project_detail(
        self,
        project_id: str,
    ) -> AdminProjectDetail | None:
        """
        Mengambil detail Project berikut
        pemilik dan agreement.

        Jika belum ada agreement:
            agreed_price = None
            assigned_freelancer_id = None
        """

        statement = text(
            _PROJECT_SELECT.rstrip()
            + ", p.description, "
            "p.published_at, "
            "p.started_at, "
            "p.completed_at, "
            "agreement.agreed_price "
            + _PROJECT_JOINS
            + " WHERE p.id = :id"
        )

        row = self._session.execute(
            statement,
            {
                "id": project_id,
            },
        ).mappings().one_or_none()

        if row is None:
            return None

        return AdminProjectDetail(
            project=_project_from_row(row),
            description=row["description"],
            agreed_price=(
                int(row["agreed_price"])
                if row["agreed_price"] is not None
                else None
            ),
            published_at=_utc_datetime(
                row["published_at"]
            ),
            started_at=_utc_datetime(
                row["started_at"]
            ),
            completed_at=_utc_datetime(
                row["completed_at"]
            ),
        )

    # ========================================================
    # 7. GET SYSTEM STATISTICS
    # ========================================================

    def get_system_statistics(
        self,
    ) -> AdminSystemStatistics:
        """
        Mengambil seluruh agregasi statistik.

        total_transactions:
            Menghitung seluruh record payments.

        platform_income:
            Hanya menjumlahkan platform_fee_amount
            dari pembayaran berstatus BERHASIL.

        Subquery terpisah mencegah duplikasi
        hasil perhitungan akibat JOIN.
        """

        statement = text(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM users
                    WHERE LOWER(role) = 'umkm'
                ) AS total_umkm,

                (
                    SELECT COUNT(*)
                    FROM users
                    WHERE LOWER(role) = 'freelancer'
                ) AS total_freelancers,

                (
                    SELECT COUNT(*)
                    FROM projects
                ) AS total_projects,

                (
                    SELECT COUNT(*)
                    FROM projects
                    WHERE UPPER(status) = 'SELESAI'
                ) AS completed_projects,

                (
                    SELECT COUNT(*)
                    FROM payments
                ) AS total_transactions,

                (
                    SELECT COALESCE(
                        SUM(
                            CASE
                                WHEN UPPER(status) = 'BERHASIL'
                                THEN platform_fee_amount
                                ELSE 0
                            END
                        ),
                        0
                    )
                    FROM payments
                ) AS platform_income
            """
        )

        row = self._session.execute(
            statement
        ).mappings().one()

        return build_system_statistics(
            total_umkm=int(
                row["total_umkm"]
            ),
            total_freelancers=int(
                row["total_freelancers"]
            ),
            total_projects=int(
                row["total_projects"]
            ),
            completed_projects=int(
                row["completed_projects"]
            ),
            total_transactions=int(
                row["total_transactions"]
            ),
            platform_income=int(
                row["platform_income"]
            ),
        )