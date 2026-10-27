from app.modules.skills.domain.repositories import (
    MasterDataRepository,
)


class ListMasterData:

    def __init__(self, repository: MasterDataRepository):
        self._repository = repository

    def get_skills(self):
        return self._repository.list_skills()

    def get_categories(self):
        return self._repository.list_categories()