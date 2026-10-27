from app.modules.skills.application.use_cases import ListMasterData
from app.modules.skills.domain.entities import Skill, ProjectCategory


class FakeMasterDataRepository:
    """
    Repository palsu untuk pengujian.
    Tidak membutuhkan koneksi MySQL.
    """

    def list_skills(self):
        return [
            Skill(id="logo_design", name="Desain Logo"),
            Skill(id="web_programming", name="Pemrograman Web"),
        ]

    def list_categories(self):
        return [
            ProjectCategory(
                id="graphic_design",
                name="Desain Grafis",
                description="Desain logo dan identitas merek",
                is_active=True,
            ),
            ProjectCategory(
                id="website",
                name="Website",
                description="Pembuatan website",
                is_active=True,
            ),
        ]


def test_get_skills():
    repository = FakeMasterDataRepository()
    use_case = ListMasterData(repository)

    result = use_case.get_skills()

    assert len(result) == 2
    assert result[0].id == "logo_design"
    assert result[1].name == "Pemrograman Web"


def test_get_categories():
    repository = FakeMasterDataRepository()
    use_case = ListMasterData(repository)

    result = use_case.get_categories()

    assert len(result) == 2
    assert result[0].name == "Desain Grafis"
    assert result[1].is_active is True


def test_get_skills_empty():
    class EmptyRepository:
        def list_skills(self):
            return []

        def list_categories(self):
            return []

    use_case = ListMasterData(EmptyRepository())

    result = use_case.get_skills()

    assert result == []