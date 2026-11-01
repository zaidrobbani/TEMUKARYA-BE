import pytest

from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
)

from app.modules.profiles.domain.entities import (
    FreelancerProfile,
)

from app.modules.profiles.application.dto import (
    SetFreelancerSkillsInput,
)

from app.modules.profiles.application.use_cases import (
    SetFreelancerSkills,
    GetFreelancerSkills,
)


class FakeProfileRepository:

    def __init__(self, profile_exists=True):
        self.profile_exists = profile_exists

    def get_by_user_id(self, user_id):
        if not self.profile_exists:
            return None

        return FreelancerProfile(
            user_id=user_id,
            professional_title="Graphic Designer",
            city="Malang",
        )


class FakeSkillsRepository:

    def __init__(self):
        self.available_ids = {
            "logo_design",
            "photo_editing",
            "web_programming",
        }
        self.saved = {}
        self.replace_called = False

    def get_existing_skill_ids(self, skill_ids):
        return set(skill_ids) & self.available_ids

    def get_skill_ids(self, freelancer_id):
        return self.saved.get(freelancer_id, [])

    def replace_skills(self, freelancer_id, skill_ids):
        self.replace_called = True
        self.saved[freelancer_id] = list(skill_ids)


class FakeUnitOfWork:

    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True


def setup_use_case(profile_exists=True):
    profile_repo = FakeProfileRepository(profile_exists)
    skills_repo = FakeSkillsRepository()
    uow = FakeUnitOfWork()

    use_case = SetFreelancerSkills(
        profile_repository=profile_repo,
        skills_repository=skills_repo,
        uow=uow,
    )

    return use_case, skills_repo, uow


# TEST 1: Berhasil menyimpan daftar keahlian
def test_set_skills_success():
    use_case, repo, uow = setup_use_case()

    result = use_case.execute(
        "freelancer-uuid-test",
        SetFreelancerSkillsInput(
            skill_ids=["logo_design", "photo_editing"]
        ),
    )

    assert result == ["logo_design", "photo_editing"]
    assert repo.get_skill_ids("freelancer-uuid-test") == result
    assert uow.committed is True


# TEST 2: Profil freelancer tidak ditemukan
def test_set_skills_profile_not_found():
    use_case, repo, uow = setup_use_case(
        profile_exists=False
    )

    with pytest.raises(NotFoundError):
        use_case.execute(
            "freelancer-uuid-test",
            SetFreelancerSkillsInput(
                skill_ids=["logo_design"]
            ),
        )

    assert repo.replace_called is False
    assert uow.committed is False


# TEST 3: Skill tidak terdaftar di master data
def test_set_skills_invalid_id():
    use_case, repo, uow = setup_use_case()

    with pytest.raises(BadRequestError):
        use_case.execute(
            "freelancer-uuid-test",
            SetFreelancerSkillsInput(
                skill_ids=["skill_tidak_ada"]
            ),
        )

    assert repo.replace_called is False
    assert uow.committed is False


# TEST 4: Skill duplikat ditolak
def test_set_skills_duplicate():
    use_case, repo, uow = setup_use_case()

    with pytest.raises(BadRequestError):
        use_case.execute(
            "freelancer-uuid-test",
            SetFreelancerSkillsInput(
                skill_ids=["logo_design", "logo_design"]
            ),
        )

    assert repo.replace_called is False
    assert uow.committed is False


# TEST 5: Daftar kosong diperbolehkan
def test_set_skills_empty_list():
    use_case, repo, uow = setup_use_case()

    result = use_case.execute(
        "freelancer-uuid-test",
        SetFreelancerSkillsInput(skill_ids=[]),
    )

    assert result == []
    assert repo.replace_called is True
    assert uow.committed is True


# TEST 6: Skill ID yang hanya berisi spasi ditolak
def test_set_skills_blank_id():
    use_case, repo, uow = setup_use_case()

    with pytest.raises(BadRequestError):
        use_case.execute(
            "freelancer-uuid-test",
            SetFreelancerSkillsInput(
                skill_ids=["   "]
            ),
        )

    assert repo.replace_called is False
    assert uow.committed is False



# TEST 7: Berhasil mengambil skill Freelancer
def test_get_freelancer_skills_success():
    profile_repo = FakeProfileRepository()
    skills_repo = FakeSkillsRepository()

    skills_repo.saved["freelancer-uuid-test"] = [
        "logo_design",
        "photo_editing",
    ]

    use_case = GetFreelancerSkills(
        profile_repository=profile_repo,
        skills_repository=skills_repo,
    )

    result = use_case.execute("freelancer-uuid-test")

    assert result == ["logo_design", "photo_editing"]


# TEST 8: Freelancer belum mempunyai skill
def test_get_freelancer_skills_empty():
    profile_repo = FakeProfileRepository()
    skills_repo = FakeSkillsRepository()

    use_case = GetFreelancerSkills(
        profile_repository=profile_repo,
        skills_repository=skills_repo,
    )

    result = use_case.execute("freelancer-uuid-test")

    assert result == []


# TEST 9: Profil Freelancer tidak ditemukan
def test_get_freelancer_skills_profile_not_found():
    profile_repo = FakeProfileRepository(
        profile_exists=False
    )
    skills_repo = FakeSkillsRepository()

    use_case = GetFreelancerSkills(
        profile_repository=profile_repo,
        skills_repository=skills_repo,
    )

    with pytest.raises(NotFoundError):
        use_case.execute("freelancer-uuid-test")