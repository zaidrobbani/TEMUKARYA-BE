from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.skills.domain.entities import (
    Skill,
    ProjectCategory,
)


class SqlAlchemyMasterDataRepository:

    def __init__(self, session: Session):
        self._session = session

    def list_skills(self) -> list[Skill]:
        query = text("""
            SELECT id, name
            FROM skills
            ORDER BY name ASC
        """)

        rows = self._session.execute(
            query
        ).mappings().all()

        return [
            Skill(
                id=row["id"],
                name=row["name"]
            )
            for row in rows
        ]

    def list_categories(self) -> list[ProjectCategory]:
        query = text("""
            SELECT id, name, description, is_active
            FROM project_categories
            WHERE is_active = 1
            ORDER BY name ASC
        """)

        rows = self._session.execute(
            query
        ).mappings().all()

        return [
            ProjectCategory(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                is_active=bool(row["is_active"])
            )
            for row in rows
        ]