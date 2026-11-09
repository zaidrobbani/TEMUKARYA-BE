
from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_handlers import register_error_handlers
from app.core.exceptions import ConflictError, NotFoundError

from app.modules.projects.application.use_cases import DeleteProject
from app.modules.projects.domain.entities import Project

from app.modules.projects.presentation.dependencies import (
    AuthenticatedProjectUser,
    get_authenticated_project_user,
    get_delete_project_use_case,
)
from app.modules.projects.presentation.router import router
from app.modules.users.domain.entities import UserRole


UMKM_A = "11111111-1111-4111-8111-111111111111"
UMKM_B = "22222222-2222-4222-8222-222222222222"
PROJECT_ID = "33333333-3333-4333-8333-333333333333"


# ============================================================
# TEST DATA
# ============================================================

def make_project():
    return Project(
        id=PROJECT_ID,
        umkm_id=UMKM_A,
        category_id="website",
        title="Website UMKM",
        description="Pembuatan website UMKM",
        budget=3000000,
        deadline=date(2026, 12, 31),
        status="TERBUKA",
    )


# ============================================================
# FAKE REPOSITORY
# ============================================================

class FakeProjectRepository:
    def __init__(self, project=None):
        self.project = project
        self.delete_calls = []
        self.can_delete = True

    def get_by_id(self, project_id):
        if self.project is None:
            return None

        if self.project.id != project_id:
            return None

        return self.project

    def delete(self, project_id, umkm_id):
        self.delete_calls.append((project_id, umkm_id))

        if not self.can_delete:
            return False

        if self.project is None:
            return False

        if self.project.id != project_id:
            return False

        if self.project.umkm_id != umkm_id:
            return False

        self.project = None
        return True


class FakeUnitOfWork:
    def __init__(self):
        self.commit_count = 0

    def commit(self):
        self.commit_count += 1


def setup_use_case(project=None):
    repository = FakeProjectRepository(project)
    uow = FakeUnitOfWork()

    use_case = DeleteProject(
        project_repository=repository,
        uow=uow,
    )

    return use_case, repository, uow


# ============================================================
# APPLICATION LAYER TESTS
# ============================================================

def test_owner_can_delete_open_project():
    use_case, repository, uow = setup_use_case(
        make_project()
    )

    use_case.execute(
        umkm_id=UMKM_A,
        project_id=PROJECT_ID,
    )

    assert repository.project is None
    assert repository.delete_calls == [
        (PROJECT_ID, UMKM_A)
    ]
    assert uow.commit_count == 1


def test_other_umkm_cannot_delete_project():
    use_case, repository, uow = setup_use_case(
        make_project()
    )

    with pytest.raises(NotFoundError):
        use_case.execute(
            umkm_id=UMKM_B,
            project_id=PROJECT_ID,
        )

    assert repository.delete_calls == []
    assert uow.commit_count == 0


def test_missing_project_cannot_be_deleted():
    use_case, repository, uow = setup_use_case()

    with pytest.raises(NotFoundError):
        use_case.execute(
            umkm_id=UMKM_A,
            project_id=PROJECT_ID,
        )

    assert repository.delete_calls == []
    assert uow.commit_count == 0


def test_started_project_cannot_be_deleted():
    project = replace(
        make_project(),
        status="BERJALAN",
    )

    use_case, repository, uow = setup_use_case(project)

    with pytest.raises(ConflictError):
        use_case.execute(
            umkm_id=UMKM_A,
            project_id=PROJECT_ID,
        )

    assert repository.delete_calls == []
    assert uow.commit_count == 0


def test_project_with_started_at_cannot_be_deleted():
    from datetime import datetime

    project = replace(
        make_project(),
        started_at=datetime(2026, 11, 2, 10, 0),
    )

    use_case, repository, uow = setup_use_case(project)

    with pytest.raises(ConflictError):
        use_case.execute(
            umkm_id=UMKM_A,
            project_id=PROJECT_ID,
        )

    assert repository.delete_calls == []
    assert uow.commit_count == 0


def test_delete_blocked_by_related_data():
    use_case, repository, uow = setup_use_case(
        make_project()
    )

    # Simulasi repository menemukan relasi yang
    # menghalangi penghapusan, misalnya lamaran.
    repository.can_delete = False

    with pytest.raises(ConflictError):
        use_case.execute(
            umkm_id=UMKM_A,
            project_id=PROJECT_ID,
        )

    assert repository.project is not None
    assert repository.delete_calls == [
        (PROJECT_ID, UMKM_A)
    ]
    assert uow.commit_count == 0


# ============================================================
# HTTP ROUTER TESTS
# ============================================================

@pytest.fixture
def http_context():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)

    repository = FakeProjectRepository(
        make_project()
    )
    uow = FakeUnitOfWork()

    use_case = DeleteProject(
        project_repository=repository,
        uow=uow,
    )

    app.dependency_overrides[
        get_delete_project_use_case
    ] = lambda: use_case

    with TestClient(app) as client:
        yield app, client, repository, uow

    app.dependency_overrides.clear()


def authenticate(app, role, user_id):
    app.dependency_overrides[
        get_authenticated_project_user
    ] = lambda: AuthenticatedProjectUser(
        user_id=user_id,
        role=role,
    )


def test_delete_requires_authentication(http_context):
    app, client, repository, uow = http_context

    response = client.delete(
        f"/projects/{PROJECT_ID}"
    )

    assert response.status_code == 401
    assert repository.delete_calls == []
    assert uow.commit_count == 0


def test_freelancer_cannot_delete_project(http_context):
    app, client, repository, uow = http_context

    authenticate(
        app,
        UserRole.FREELANCER,
        UMKM_B,
    )

    response = client.delete(
        f"/projects/{PROJECT_ID}"
    )

    assert response.status_code == 403
    assert repository.delete_calls == []
    assert uow.commit_count == 0


def test_owner_delete_returns_200(http_context):
    app, client, repository, uow = http_context

    authenticate(
        app,
        UserRole.UMKM,
        UMKM_A,
    )

    response = client.delete(
        f"/projects/{PROJECT_ID}"
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Project berhasil dihapus", "data": None}
    assert repository.project is None
    assert uow.commit_count == 1


def test_other_umkm_delete_returns_404(http_context):
    app, client, repository, uow = http_context

    authenticate(
        app,
        UserRole.UMKM,
        UMKM_B,
    )

    response = client.delete(
        f"/projects/{PROJECT_ID}"
    )

    assert response.status_code == 404
    assert repository.project is not None
    assert uow.commit_count == 0


def test_delete_blocked_returns_409(http_context):
    app, client, repository, uow = http_context

    authenticate(
        app,
        UserRole.UMKM,
        UMKM_A,
    )

    repository.can_delete = False

    response = client.delete(
        f"/projects/{PROJECT_ID}"
    )

    assert response.status_code == 409
    assert repository.project is not None
    assert uow.commit_count == 0