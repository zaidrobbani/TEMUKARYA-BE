from datetime import date, datetime

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.modules.discovery.domain.entities import (
    FreelancerDetail,
    FreelancerPortfolio,
    FreelancerReview,
    FreelancerSearchFilters,
    FreelancerSkill,
    FreelancerSummary,
    FreelancerWorkExperience,
)

from app.modules.discovery.domain.repositories import (
    DiscoveryRepository,
)


# ============================================================
# BASE FREELANCER QUERY
# ============================================================

# Pengalaman dan rating dihitung melalui subquery.
# Tujuannya agar seorang Freelancer tidak muncul
# berulang ketika memiliki banyak skill atau review.

_BASE_QUERY = """
    SELECT
        fp.user_id,
        u.name,
        fp.professional_title,
        fp.city,
        fp.availability_status,
        fp.service_price_min,
        fp.service_price_max,
        fp.bio,
        COALESCE(
            exp.experience_count, 0
        ) AS experience_count,
        ratings.average_rating,
        COALESCE(
            ratings.review_count, 0
        ) AS review_count

    FROM freelancer_profiles AS fp

    JOIN users AS u
        ON u.id = fp.user_id

    LEFT JOIN (
        SELECT
            freelancer_id,
            COUNT(*) AS experience_count
        FROM freelancer_experiences
        GROUP BY freelancer_id
    ) AS exp
        ON exp.freelancer_id = fp.user_id

    LEFT JOIN (
        SELECT
            pa.freelancer_id,
            AVG(fr.rating) AS average_rating,
            COUNT(*) AS review_count

        FROM project_agreements AS pa

        JOIN freelancer_reviews AS fr
            ON fr.project_id = pa.project_id

        GROUP BY pa.freelancer_id
    ) AS ratings
        ON ratings.freelancer_id = fp.user_id

    WHERE LOWER(u.role) = 'freelancer'
"""


# ============================================================
# DATA CONVERSION HELPERS
# ============================================================

def _escape_like(value: str) -> str:
    """
    Memastikan karakter %, _, dan !
    diperlakukan sebagai teks pencarian biasa.

    Ini bukan pengganti query parameter.
    Query tetap menggunakan SQL bind parameters.
    """

    return (
        value.replace("!", "!!")
        .replace("%", "!%")
        .replace("_", "!_")
    )


def _as_date(
    value: date | str | None,
) -> date | None:

    if value is None or isinstance(value, date):
        return value

    return date.fromisoformat(value)


def _as_datetime(
    value: datetime | str | None,
) -> datetime | None:

    if value is None or isinstance(value, datetime):
        return value

    return datetime.fromisoformat(value)


# ============================================================
# DISCOVERY REPOSITORY
# ============================================================

class SqlAlchemyDiscoveryRepository(DiscoveryRepository):
    """
    Implementasi Discovery Repository.

    Repository ini READ-ONLY:
    - Tidak membuat Freelancer
    - Tidak memperbarui profil
    - Tidak menghapus data
    - Tidak melakukan commit

    Semua operasi hanya membaca database.
    """

    def __init__(
        self,
        session: Session,
    ):
        self._session = session

    # ========================================================
    # 1. LOAD FREELANCER SKILLS
    # ========================================================

    def _load_skills(
        self,
        freelancer_ids: list[str],
    ) -> dict[str, tuple[FreelancerSkill, ...]]:
        """
        Mengambil skills banyak Freelancer
        dalam satu query.

        Menghindari N+1 query.
        """

        if not freelancer_ids:
            return {}

        query = text("""
            SELECT
                fs.freelancer_id,
                s.id,
                s.name

            FROM freelancer_skills AS fs

            JOIN skills AS s
                ON s.id = fs.skill_id

            WHERE fs.freelancer_id IN :freelancer_ids

            ORDER BY
                fs.freelancer_id,
                LOWER(s.name),
                s.id
        """).bindparams(
            bindparam(
                "freelancer_ids",
                expanding=True,
            )
        )

        rows = self._session.execute(
            query,
            {
                "freelancer_ids": freelancer_ids,
            },
        ).mappings().all()

        grouped: dict[
            str,
            list[FreelancerSkill],
        ] = {
            freelancer_id: []
            for freelancer_id in freelancer_ids
        }

        for row in rows:

            grouped[
                str(row["freelancer_id"])
            ].append(
                FreelancerSkill(
                    id=str(row["id"]),
                    name=row["name"],
                )
            )

        return {
            key: tuple(value)
            for key, value in grouped.items()
        }

    # ========================================================
    # 2. CONVERT DATABASE ROW TO SUMMARY
    # ========================================================

    @staticmethod
    def _to_summary(
        row,
        skills: tuple[FreelancerSkill, ...],
    ) -> FreelancerSummary:

        return FreelancerSummary(
            user_id=str(row["user_id"]),
            name=row["name"],
            professional_title=(
                row["professional_title"]
            ),
            city=row["city"],
            availability_status=(
                row["availability_status"]
            ),
            service_price_min=(
                row["service_price_min"]
            ),
            service_price_max=(
                row["service_price_max"]
            ),
            skills=skills,
            experience_count=int(
                row["experience_count"]
            ),
            average_rating=(
                float(row["average_rating"])
                if row["average_rating"] is not None
                else None
            ),
            review_count=int(
                row["review_count"]
            ),
        )

    # ========================================================
    # 3. SEARCH FREELANCERS
    # ========================================================

    def search_freelancers(
        self,
        filters: FreelancerSearchFilters,
        limit: int,
        offset: int,
    ) -> list[FreelancerSummary]:

        sql = _BASE_QUERY

        params: dict = {
            "limit": limit,
            "offset": offset,
        }

        expanding_skills = False

        # ====================================================
        # AVAILABILITY FILTER
        # ====================================================

        if filters.availability_status is not None:

            sql += """
                AND fp.availability_status =
                    :availability_status
            """

            params["availability_status"] = (
                filters.availability_status
            )

        # ====================================================
        # CITY FILTER
        # ====================================================

        if filters.city is not None:

            sql += """
                AND LOWER(fp.city) = LOWER(:city)
            """

            params["city"] = filters.city

        # ====================================================
        # NAME / PROFESSION / SKILL SEARCH
        # ====================================================

        if filters.search is not None:

            sql += """
                AND (
                    LOWER(u.name)
                        LIKE :search_text ESCAPE '!'

                    OR LOWER(fp.professional_title)
                        LIKE :search_text ESCAPE '!'

                    OR EXISTS (
                        SELECT 1

                        FROM freelancer_skills
                            AS fs_search

                        JOIN skills AS s_search
                            ON s_search.id =
                                fs_search.skill_id

                        WHERE fs_search.freelancer_id =
                            fp.user_id

                        AND LOWER(s_search.name)
                            LIKE :search_text ESCAPE '!'
                    )
                )
            """

            params["search_text"] = (
                "%"
                + _escape_like(
                    filters.search.lower()
                )
                + "%"
            )

        # ====================================================
        # SKILL FILTER
        # ====================================================

        if filters.skill_ids:

            sql += """
                AND EXISTS (
                    SELECT 1

                    FROM freelancer_skills AS fs_filter

                    WHERE fs_filter.freelancer_id =
                        fp.user_id

                    AND fs_filter.skill_id IN :skill_ids
                )
            """

            params["skill_ids"] = list(
                filters.skill_ids
            )

            expanding_skills = True

        # ====================================================
        # PRICE RANGE FILTER
        # ====================================================

        # Harga Freelancer dianggap cocok jika
        # rentang jasanya beririsan dengan
        # rentang yang dicari UMKM.
        #
        # Jika batas yang diperlukan belum diisi,
        # Freelancer tidak lolos filter tersebut.

        if filters.min_price is not None:

            sql += """
                AND fp.service_price_max IS NOT NULL

                AND fp.service_price_max >= :min_price
            """

            params["min_price"] = (
                filters.min_price
            )

        if filters.max_price is not None:

            sql += """
                AND fp.service_price_min IS NOT NULL

                AND fp.service_price_min <= :max_price
            """

            params["max_price"] = (
                filters.max_price
            )

        # ====================================================
        # EXPERIENCE FILTER
        # ====================================================

        if filters.min_experience_count is not None:

            sql += """
                AND COALESCE(
                    exp.experience_count, 0
                ) >= :min_experience_count
            """

            params["min_experience_count"] = (
                filters.min_experience_count
            )

        # ====================================================
        # RATING FILTER
        # ====================================================

        if filters.min_rating is not None:

            sql += """
                AND COALESCE(
                    ratings.review_count, 0
                ) > 0

                AND ratings.average_rating >= :min_rating
            """

            params["min_rating"] = filters.min_rating

        # ====================================================
        # SORTING & PAGINATION
        # ====================================================

        sql += """
            ORDER BY
                LOWER(u.name),
                fp.user_id

            LIMIT :limit
            OFFSET :offset
        """

        statement = text(sql)

        if expanding_skills:

            statement = statement.bindparams(
                bindparam(
                    "skill_ids",
                    expanding=True,
                )
            )

        rows = self._session.execute(
            statement,
            params,
        ).mappings().all()

        # ====================================================
        # BULK LOAD RELATED SKILLS
        # ====================================================

        freelancer_ids = [
            str(row["user_id"])
            for row in rows
        ]

        skills_by_user = self._load_skills(
            freelancer_ids
        )

        # ====================================================
        # BUILD DOMAIN ENTITIES
        # ====================================================

        return [
            self._to_summary(
                row,
                skills_by_user.get(
                    str(row["user_id"]),
                    (),
                ),
            )
            for row in rows
        ]

    # ========================================================
    # 4. GET FREELANCER DETAIL
    # ========================================================

    def get_freelancer_detail(
        self,
        freelancer_id: str,
    ) -> FreelancerDetail | None:

        # ====================================================
        # GET BASIC PROFILE
        # ====================================================

        statement = text(
            _BASE_QUERY
            + " AND fp.user_id = :freelancer_id"
        )

        row = self._session.execute(
            statement,
            {
                "freelancer_id": freelancer_id,
            },
        ).mappings().first()

        if row is None:
            return None

        # ====================================================
        # GET SKILLS
        # ====================================================

        skills = self._load_skills(
            [freelancer_id]
        ).get(
            freelancer_id,
            (),
        )

        summary = self._to_summary(
            row,
            skills,
        )

        # ====================================================
        # GET EXPERIENCES
        # ====================================================

        experiences = self._session.execute(
            text("""
                SELECT
                    id,
                    job_title,
                    organization_name,
                    description,
                    start_date,
                    end_date

                FROM freelancer_experiences

                WHERE freelancer_id = :freelancer_id

                ORDER BY start_date DESC, id
            """),
            {
                "freelancer_id": freelancer_id,
            },
        ).mappings().all()

        # ====================================================
        # GET PORTFOLIOS
        # ====================================================

        portfolios = self._session.execute(
            text("""
                SELECT
                    id,
                    title,
                    description,
                    project_url

                FROM portfolios

                WHERE freelancer_id = :freelancer_id

                ORDER BY created_at DESC, id
            """),
            {
                "freelancer_id": freelancer_id,
            },
        ).mappings().all()

        # ====================================================
        # GET REVIEWS
        # ====================================================

        reviews = self._session.execute(
            text("""
                SELECT
                    fr.id,
                    fr.project_id,
                    fr.rating,
                    fr.review_text,
                    fr.created_at

                FROM freelancer_reviews AS fr

                JOIN project_agreements AS pa
                    ON pa.project_id = fr.project_id

                WHERE pa.freelancer_id = :freelancer_id

                ORDER BY
                    fr.created_at DESC,
                    fr.id
            """),
            {
                "freelancer_id": freelancer_id,
            },
        ).mappings().all()

        # ====================================================
        # BUILD FREELANCER DETAIL
        # ====================================================

        return FreelancerDetail(
            **{
                name: getattr(summary, name)
                for name in (
                    "user_id",
                    "name",
                    "professional_title",
                    "city",
                    "availability_status",
                    "service_price_min",
                    "service_price_max",
                    "skills",
                    "experience_count",
                    "average_rating",
                    "review_count",
                )
            },
            bio=row["bio"],
            experiences=tuple(
                FreelancerWorkExperience(
                    id=str(item["id"]),
                    job_title=item["job_title"],
                    organization_name=(
                        item["organization_name"]
                    ),
                    description=item["description"],
                    start_date=_as_date(
                        item["start_date"]
                    ),
                    end_date=_as_date(
                        item["end_date"]
                    ),
                )
                for item in experiences
            ),
            portfolios=tuple(
                FreelancerPortfolio(
                    id=str(item["id"]),
                    title=item["title"],
                    description=item["description"],
                    project_url=item["project_url"],
                )
                for item in portfolios
            ),
            reviews=tuple(
                FreelancerReview(
                    id=str(item["id"]),
                    project_id=str(item["project_id"]),
                    rating=int(item["rating"]),
                    review_text=item["review_text"],
                    created_at=_as_datetime(
                        item["created_at"]
                    ),
                )
                for item in reviews
            ),
        )