from datetime import date, datetime, timezone

from sqlalchemy import RowMapping, text
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
from app.core.sql_types import SqlParams


def _utc_datetime(
    value: datetime | str | None,
) -> datetime | None:
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
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return date.fromisoformat(value)


def _like_pattern(
    query: str,
) -> str:
    escaped = (
        query.lower()
        .replace("!", "!!")
        .replace("%", "!%")
        .replace("_", "!_")
    )

    return f"%{escaped}%"


def _user_from_row(
    row: RowMapping,
) -> AdminUserSummary:
    return AdminUserSummary(
        id=str(row["id"]),
        name=row["name"],
        email=row["email"],
        role=row["role"],
        created_at=_utc_datetime(
            row["created_at"]
        ),
    )


def _project_from_row(
    row: RowMapping,
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


class SqlAlchemyAdminStatisticsRepository:
    def __init__(
        self,
        session: Session,
    ):
        self._session = session

    @staticmethod
    def _user_filter(
        role: str | None,
        search: str | None,
    ) -> tuple[str, SqlParams]:
        conditions: list[str] = []
        params: SqlParams = {}

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

    @staticmethod
    def _project_filter(
        status: str | None,
        search: str | None,
    ) -> tuple[str, SqlParams]:
        conditions: list[str] = []
        params: SqlParams = {}

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

    def list_users(
        self,
        *,
        role: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[AdminUserSummary, ...]:
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

    def get_user_detail(
        self,
        user_id: str,
    ) -> AdminUserDetail | None:
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

        return AdminUserDetail(
            user=user,
            umkm_profile=umkm_profile,
            freelancer_profile=freelancer_profile,
        )

    def list_projects(
        self,
        *,
        status: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[AdminProjectSummary, ...]:
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

    def count_projects(
        self,
        *,
        status: str | None,
        search: str | None,
    ) -> int:
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

    def get_project_detail(
        self,
        project_id: str,
    ) -> AdminProjectDetail | None:
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

    def get_system_statistics(
        self,
    ) -> AdminSystemStatistics:
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
