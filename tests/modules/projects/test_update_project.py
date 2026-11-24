
from dataclasses import replace
from datetime import date, datetime

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.projects.application.dto import UpdateProjectInput
from app.modules.projects.application.use_cases import UpdateProject
from app.modules.projects.domain.entities import Project


UMKM_A = "11111111-1111-4111-8111-111111111111"
UMKM_B = "22222222-2222-4222-8222-222222222222"
PROJECT_ID = "33333333-3333-4333-8333-333333333333"


# ============================================================
# FAKE REPOSITORY
# ============================================================

class FakeProjectRepository:
    def __init__(self, project=None):
        self.project = project
        self.updated_project = None
        self.updated_skills = None
        self.update_calls = 0
        self.update_result_none = False

    def get_by_id(self, project_id):
        if self.project is None:
            return None

        return (
            self.project
            if self.project.id == project_id
            else None
        )

    def is_active_category(self, category_id):
        return category_id == "website"

    def get_existing_skill_ids(self, skill_ids):
        available = {"python", "fastapi"}
        return set(skill_ids) & available

    def update(self, project, skill_ids):
        self.update_calls += 1

        if self.update_result_none:
            return None

        self.updated_project = project
        self.updated_skills = skill_ids

        return project


# ============================================================
# FAKE UNIT OF WORK
# ============================================================

class FakeUnitOfWork:
    def __init__(self):
        self.commit_count = 0

    def commit(self):
        self.commit_count += 1


# ============================================================
# TEST DATA HELPERS
# ============================================================

def make_project():
    return Project(
        id=PROJECT_ID,
        umkm_id=UMKM_A,
        category_id="website",
        title="Judul Lama",
        description="Deskripsi lama",
        budget=1000000,
        deadline=date(2026, 12, 1),
        status="TERBUKA",
    )


def make_input():
    return UpdateProjectInput(
        category_id="website",
        title="Judul Baru",
        description="Deskripsi baru",
        budget=3000000,
        deadline=date(2026, 12, 31),
        skill_ids=("python", "fastapi"),
    )


def setup_use_case(project=None):
    repository = FakeProjectRepository(project)
    uow = FakeUnitOfWork()

    use_case = UpdateProject(
        project_repository=repository,
        uow=uow,
    )

    return use_case, repository, uow


# ============================================================
# 1. SUCCESS
# ============================================================

def test_owner_can_update_open_project():
    use_case, repository, uow = setup_use_case(
        make_project()
    )

    result = use_case.execute(
        umkm_id=UMKM_A,
        project_id=PROJECT_ID,
        data=make_input(),
    )

    assert result.title == "Judul Baru"
    assert result.budget == 3000000
    assert result.umkm_id == UMKM_A
    assert result.status == "TERBUKA"

    assert repository.updated_skills == (
        "python",
        "fastapi",
    )

    assert repository.update_calls == 1
    assert uow.commit_count == 1


# ============================================================
# 2. OWNERSHIP
# ============================================================

def test_other_umkm_cannot_update_project():
    use_case, repository, uow = setup_use_case(
        make_project()
    )

    with pytest.raises(NotFoundError):
        use_case.execute(
            umkm_id=UMKM_B,
            project_id=PROJECT_ID,
            data=make_input(),
        )

    assert repository.update_calls == 0
    assert uow.commit_count == 0


def test_missing_project_cannot_be_updated():
    use_case, repository, uow = setup_use_case()

    with pytest.raises(NotFoundError):
        use_case.execute(
            umkm_id=UMKM_A,
            project_id=PROJECT_ID,
            data=make_input(),
        )

    assert repository.update_calls == 0
    assert uow.commit_count == 0


# ============================================================
# 3. PROJECT STATUS
# ============================================================

def test_started_project_cannot_be_updated():
    project = replace(
        make_project(),
        status="BERJALAN",
    )

    use_case, repository, uow = setup_use_case(project)

    with pytest.raises(ConflictError):
        use_case.execute(
            umkm_id=UMKM_A,
            project_id=PROJECT_ID,
            data=make_input(),
        )

    assert repository.update_calls == 0
    assert uow.commit_count == 0


def test_project_with_started_at_cannot_be_updated():
    project = replace(
        make_project(),
        started_at=datetime(2026, 11, 2, 10, 0),
    )

    use_case, repository, uow = setup_use_case(project)

    with pytest.raises(ConflictError):
        use_case.execute(
            umkm_id=UMKM_A,
            project_id=PROJECT_ID,
            data=make_input(),
        )

    assert repository.update_calls == 0
    assert uow.commit_count == 0


# ============================================================
# 4. INPUT VALIDATION
# ============================================================

def test_update_rejects_negative_budget():
    use_case, repository, uow = setup_use_case(
        make_project()
    )

    invalid_data = replace(
        make_input(),
        budget=-1000,
    )

    with pytest.raises(ValueError):
        use_case.execute(
            umkm_id=UMKM_A,
            project_id=PROJECT_ID,
            data=invalid_data,
        )

    assert repository.update_calls == 0
    assert uow.commit_count == 0


def test_update_rejects_duplicate_skills():
    use_case, repository, uow = setup_use_case(
        make_project()
    )

    invalid_data = replace(
        make_input(),
        skill_ids=("python", "python"),
    )

    with pytest.raises(ValueError):
        use_case.execute(
            umkm_id=UMKM_A,
            project_id=PROJECT_ID,
            data=invalid_data,
        )

    assert repository.update_calls == 0
    assert uow.commit_count == 0


def test_update_rejects_unknown_skill():
    use_case, repository, uow = setup_use_case(
        make_project()
    )

    invalid_data = replace(
        make_input(),
        skill_ids=("python", "unknown_skill"),
    )

    with pytest.raises(ValueError):
        use_case.execute(
            umkm_id=UMKM_A,
            project_id=PROJECT_ID,
            data=invalid_data,
        )

    assert repository.update_calls == 0
    assert uow.commit_count == 0


# ============================================================
# 5. CONCURRENT STATUS CHANGE
# ============================================================

def test_update_does_not_commit_when_state_changes():
    use_case, repository, uow = setup_use_case(
        make_project()
    )

    repository.update_result_none = True

    with pytest.raises(ConflictError):
        use_case.execute(
            umkm_id=UMKM_A,
            project_id=PROJECT_ID,
            data=make_input(),
        )

    assert repository.update_calls == 1
    assert uow.commit_count == 0