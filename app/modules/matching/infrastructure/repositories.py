from sqlalchemy import RowMapping, bindparam, text
from sqlalchemy.orm import Session

from app.modules.matching.domain.entities import (
    FreelancerMatchingSource,
    ProjectMatchingSource,
)

from app.modules.matching.domain.repositories import (
    MatchingRepository,
)


class SqlAlchemyMatchingRepository(MatchingRepository):
    def __init__(
        self,
        session: Session,
    ):
        self._session = session

    def _project_skill_map(
        self,
        project_ids: list[str],
    ) -> dict[str, tuple[str, ...]]:
        if not project_ids:
            return {}

        statement = text("""
            SELECT
                project_id,
                skill_id

            FROM project_skills

            WHERE project_id IN :project_ids

            ORDER BY project_id, skill_id
        """).bindparams(
            bindparam(
                "project_ids",
                expanding=True,
            )
        )

        rows = self._session.execute(
            statement,
            {"project_ids": project_ids},
        ).mappings().all()

        grouped: dict[
            str, list[str]
        ] = {
            project_id: []
            for project_id in project_ids
        }

        for row in rows:
            project_id = str(row["project_id"])

            grouped[project_id].append(
                str(row["skill_id"])
            )

        return {
            key: tuple(value)
            for key, value in grouped.items()
        }

    def _freelancer_skill_map(
        self,
        freelancer_ids: list[str],
    ) -> dict[str, tuple[str, ...]]:
        if not freelancer_ids:
            return {}

        statement = text("""
            SELECT
                freelancer_id,
                skill_id

            FROM freelancer_skills

            WHERE freelancer_id IN :freelancer_ids

            ORDER BY freelancer_id, skill_id
        """).bindparams(
            bindparam(
                "freelancer_ids",
                expanding=True,
            )
        )

        rows = self._session.execute(
            statement,
            {"freelancer_ids": freelancer_ids},
        ).mappings().all()

        grouped: dict[
            str, list[str]
        ] = {
            freelancer_id: []
            for freelancer_id in freelancer_ids
        }

        for row in rows:
            freelancer_id = str(
                row["freelancer_id"]
            )

            grouped[freelancer_id].append(
                str(row["skill_id"])
            )

        return {
            key: tuple(value)
            for key, value in grouped.items()
        }

    @staticmethod
    def _to_project(
        row: RowMapping,
        skills: tuple[str, ...],
    ) -> ProjectMatchingSource:
        return ProjectMatchingSource(
            project_id=str(row["id"]),
            umkm_id=str(row["umkm_id"]),
            title=row["title"],
            category_id=str(row["category_id"]),
            status=row["status"],
            required_skill_ids=skills,
        )

    @staticmethod
    def _to_freelancer(
        row: RowMapping,
        skills: tuple[str, ...],
    ) -> FreelancerMatchingSource:
        return FreelancerMatchingSource(
            freelancer_id=str(row["user_id"]),
            name=row["name"],
            professional_title=(
                row["professional_title"]
            ),
            city=row["city"],
            availability_status=(
                row["availability_status"]
            ),
            skill_ids=skills,
            service_price_min=(
                row["service_price_min"]
            ),
            service_price_max=(
                row["service_price_max"]
            ),
        )

    def get_project(
        self,
        project_id: str,
    ) -> ProjectMatchingSource | None:
        statement = text("""
            SELECT
                id,
                umkm_id,
                title,
                category_id,
                status

            FROM projects

            WHERE id = :project_id
        """)

        row = self._session.execute(
            statement,
            {"project_id": project_id},
        ).mappings().one_or_none()

        if row is None:
            return None

        project_id = str(row["id"])

        skills = self._project_skill_map(
            [project_id]
        )[project_id]

        return self._to_project(
            row,
            skills,
        )

    def get_freelancer(
        self,
        freelancer_id: str,
    ) -> FreelancerMatchingSource | None:
        statement = text("""
            SELECT
                fp.user_id,
                u.name,
                fp.professional_title,
                fp.city,
                fp.availability_status,
                fp.service_price_min,
                fp.service_price_max

            FROM freelancer_profiles AS fp

            JOIN users AS u
                ON u.id = fp.user_id

            WHERE fp.user_id = :freelancer_id

              AND LOWER(u.role) = 'freelancer'
        """)

        row = self._session.execute(
            statement,
            {"freelancer_id": freelancer_id},
        ).mappings().one_or_none()

        if row is None:
            return None

        freelancer_id = str(row["user_id"])

        skills = self._freelancer_skill_map(
            [freelancer_id]
        )[freelancer_id]

        return self._to_freelancer(
            row,
            skills,
        )

    def iter_available_freelancers(
        self,
    ) -> list[FreelancerMatchingSource]:
        statement = text("""
            SELECT
                fp.user_id,
                u.name,
                fp.professional_title,
                fp.city,
                fp.availability_status,
                fp.service_price_min,
                fp.service_price_max

            FROM freelancer_profiles AS fp

            JOIN users AS u
                ON u.id = fp.user_id

            WHERE LOWER(u.role) = 'freelancer'

              AND fp.availability_status = 'AVAILABLE'

            ORDER BY
                LOWER(u.name),
                fp.user_id
        """)

        rows = self._session.execute(
            statement
        ).mappings().all()

        freelancer_ids = [
            str(row["user_id"])
            for row in rows
        ]

        skills = self._freelancer_skill_map(
            freelancer_ids
        )

        return [
            self._to_freelancer(
                row,
                skills[str(row["user_id"])],
            )
            for row in rows
        ]

    def iter_published_projects(
        self,
    ) -> list[ProjectMatchingSource]:
        statement = text("""
            SELECT
                id,
                umkm_id,
                title,
                category_id,
                status

            FROM projects

            WHERE status = 'TERBUKA'

              AND published_at IS NOT NULL

            ORDER BY
                published_at DESC,
                id
        """)

        rows = self._session.execute(
            statement
        ).mappings().all()

        project_ids = [
            str(row["id"])
            for row in rows
        ]

        skills = self._project_skill_map(
            project_ids
        )

        return [
            self._to_project(
                row,
                skills[str(row["id"])],
            )
            for row in rows
        ]
