from typing import Protocol

from app.modules.skills.domain.entities import (
    Skill,
    ProjectCategory,
)


class MasterDataRepository(Protocol):

    def list_skills(self) -> list[Skill]:
        ...

    def list_categories(self) -> list[ProjectCategory]:
        ...