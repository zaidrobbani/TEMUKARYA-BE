from app.modules.skills.domain.repositories import (
    MasterDataRepository,
)
from app.modules.skills.domain.entities import ProjectCategory, Skill


class ListMasterData:
    def __init__(self, repository: MasterDataRepository):
        self._repository = repository

    def get_skills(self) -> list[Skill]:
        return self._repository.list_skills()

    def get_categories(self) -> list[ProjectCategory]:
        return self._repository.list_categories()
