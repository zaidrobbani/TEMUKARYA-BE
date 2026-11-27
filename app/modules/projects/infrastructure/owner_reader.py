from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ProjectOwner:
    user_id: str
    owner_name: str
    business_name: str | None
    city: str | None
    profile_image_url: str | None


class SqlProjectOwnerReader:
    def __init__(self, session: Session):
        self._session = session

    def owners(self, umkm_ids: list[str]) -> dict[str, ProjectOwner]:
        ids = sorted(set(umkm_ids))
        if not ids:
            return {}
        rows = self._session.execute(
            text(
                "SELECT u.id, u.name, u.profile_image_url, p.business_name, p.city "
                "FROM users u LEFT JOIN umkm_profiles p ON p.user_id = u.id "
                "WHERE u.id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": ids},
        ).mappings().all()
        return {
            str(r["id"]): ProjectOwner(str(r["id"]), r["name"], r["business_name"], r["city"], r["profile_image_url"])
            for r in rows
        }

    def skill_ids(self, project_ids: list[str]) -> dict[str, list[str]]:
        ids = sorted(set(project_ids))
        if not ids:
            return {}
        rows = self._session.execute(
            text("SELECT project_id, skill_id FROM project_skills WHERE project_id IN :ids ORDER BY skill_id")
            .bindparams(bindparam("ids", expanding=True)),
            {"ids": ids},
        ).all()
        out: dict[str, list[str]] = {}
        for project_id, skill_id in rows:
            out.setdefault(str(project_id), []).append(str(skill_id))
        return out
