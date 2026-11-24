
from datetime import date, datetime

import pytest

from app.modules.projects.application.dto import CreateProjectInput
from app.modules.projects.application.use_cases import CreateProject


# ============================================================
# FAKE REPOSITORY
# ============================================================

class FakeProjectRepository:
    def __init__(self):
        self.umkm_exists = True
        self.category_active = True
        self.existing_skills = {"python", "fastapi"}

        self.saved_project = None
        self.saved_skills = []
        self.fail_add_skills = False

    def umkm_profile_exists(self, umkm_id):
        return self.umkm_exists

    def is_active_category(self, category_id):
        return self.category_active

    def get_existing_skill_ids(self, skill_ids):
        return set(skill_ids) & self.existing_skills

    def add(self, project):
        self.saved_project = project
        return project

    def add_skills(self, project_id, skill_ids):
        if self.fail_add_skills:
            raise RuntimeError("Simulated skill storage failure")

        self.saved_skills = list(skill_ids)


# ============================================================
# FAKE UNIT OF WORK
# ============================================================

class FakeUnitOfWork:
    def __init__(self):
        self.commit_count = 0

    def commit(self):
        self.commit_count += 1


# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture
def repository():
    return FakeProjectRepository()


@pytest.fixture
def uow():
    return FakeUnitOfWork()


@pytest.fixture
def create_project(repository, uow):
    return CreateProject(
        project_repository=repository,
        uow=uow,
        clock=lambda: datetime(2026, 11, 2, 10, 0, 0),
    )


@pytest.fixture
def valid_input():
    return CreateProjectInput(
        category_id="website",
        title="Pembuatan Website UMKM",
        description="Membuat website company profile",
        budget=3000000,
        deadline=date(2026, 12, 31),
        skill_ids=("python", "fastapi"),
    )


# ============================================================
# TEST CASES
# ============================================================

def test_create_project_success(
    create_project, repository, uow, valid_input
):
    project = create_project.execute(
        umkm_id="umkm-123",
        data=valid_input,
    )

    assert project.title == "Pembuatan Website UMKM"
    assert project.budget == 3000000
    assert project.umkm_id == "umkm-123"
    assert project.status == "TERBUKA"
    assert project.published_at == datetime(2026, 11, 2, 10, 0, 0)

    assert repository.saved_project == project
    assert repository.saved_skills == ["python", "fastapi"]
    assert uow.commit_count == 1


def test_create_project_rejects_negative_budget(
    create_project, uow, valid_input
):
    data = CreateProjectInput(
        **{**vars(valid_input), "budget": -1000}
    )

    with pytest.raises(ValueError, match="Budget"):
        create_project.execute("umkm-123", data)

    assert uow.commit_count == 0


def test_create_project_rejects_empty_title(
    create_project, uow, valid_input
):
    data = CreateProjectInput(
        **{**vars(valid_input), "title": "   "}
    )

    with pytest.raises(ValueError, match="Judul"):
        create_project.execute("umkm-123", data)

    assert uow.commit_count == 0


def test_create_project_rejects_inactive_category(
    create_project, repository, uow, valid_input
):
    repository.category_active = False

    with pytest.raises(ValueError, match="Kategori"):
        create_project.execute("umkm-123", valid_input)

    assert uow.commit_count == 0


def test_create_project_rejects_unknown_skills(
    create_project, uow, valid_input
):
    data = CreateProjectInput(
        **{
            **vars(valid_input),
            "skill_ids": ("python", "unknown_skill"),
        }
    )

    with pytest.raises(ValueError, match="skill"):
        create_project.execute("umkm-123", data)

    assert uow.commit_count == 0


def test_create_project_rejects_duplicate_skills(
    create_project, uow, valid_input
):
    data = CreateProjectInput(
        **{
            **vars(valid_input),
            "skill_ids": ("python", "python"),
        }
    )

    with pytest.raises(ValueError, match="duplikat"):
        create_project.execute("umkm-123", data)

    assert uow.commit_count == 0


def test_create_project_rejects_missing_umkm_profile(
    create_project, repository, uow, valid_input
):
    repository.umkm_exists = False

    with pytest.raises(ValueError, match="Profil UMKM"):
        create_project.execute("umkm-123", valid_input)

    assert uow.commit_count == 0


def test_create_project_does_not_commit_when_skills_fail(
    create_project, repository, uow, valid_input
):
    repository.fail_add_skills = True

    with pytest.raises(RuntimeError, match="skill storage failure"):
        create_project.execute("umkm-123", valid_input)

    assert uow.commit_count == 0