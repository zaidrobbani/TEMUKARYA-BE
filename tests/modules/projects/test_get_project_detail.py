from datetime import date, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_handlers import register_error_handlers
from app.core.exceptions import NotFoundError
from app.modules.projects.application.use_cases import GetProjectDetail
from app.modules.projects.domain.entities import Project
from app.modules.projects.presentation.dependencies import (
    AuthenticatedProjectUser,
    get_authenticated_project_user,
    get_project_detail_use_case,
)
from app.modules.projects.presentation.router import router
from app.modules.users.domain.entities import UserRole


UMKM_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"


def make_project(
    umkm_id=UMKM_A,
    status="TERBUKA",
    published=True,
):
    return Project(
        id=str(uuid4()),
        umkm_id=umkm_id,
        category_id="website",
        title="Website UMKM",
        description="Membangun website company profile",
        budget=3000000,
        deadline=date(2026, 12, 31),
        status=status,
        published_at=(
            datetime(2026, 11, 2, 10, 0)
            if published
            else None
        ),
    )


class FakeRepository:
    def __init__(self, project=None):
        self.project = project
        self.requested_ids = []

    def get_by_id(self, project_id):
        self.requested_ids.append(project_id)

        if self.project is None:
            return None

        if self.project.id != project_id:
            return None

        return self.project


# ============================================================
# APPLICATION USE CASE TESTS
# ============================================================

def test_owner_can_view_unpublished_project():
    project = make_project(published=False)
    use_case = GetProjectDetail(FakeRepository(project))

    result = use_case.execute(project.id, UMKM_A)

    assert result.id == project.id


def test_other_user_can_view_published_open_project():
    project = make_project()
    use_case = GetProjectDetail(FakeRepository(project))

    result = use_case.execute(project.id, USER_B)

    assert result.id == project.id


def test_other_user_cannot_view_unpublished_project():
    project = make_project(published=False)
    use_case = GetProjectDetail(FakeRepository(project))

    with pytest.raises(NotFoundError):
        use_case.execute(project.id, USER_B)


def test_other_user_cannot_view_non_open_project():
    project = make_project(status="BERJALAN")
    use_case = GetProjectDetail(FakeRepository(project))

    with pytest.raises(NotFoundError):
        use_case.execute(project.id, USER_B)


def test_missing_project_returns_not_found():
    use_case = GetProjectDetail(FakeRepository())

    with pytest.raises(NotFoundError):
        use_case.execute(str(uuid4()), UMKM_A)


# ============================================================
# HTTP ROUTER TESTS
# ============================================================

@pytest.fixture
def http_context():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)

    with TestClient(app) as client:
        yield app, client

    app.dependency_overrides.clear()


def test_detail_requires_authentication(http_context):
    app, client = http_context

    response = client.get(f"/projects/{uuid4()}")

    assert response.status_code == 401


def test_freelancer_can_view_public_project(http_context):
    app, client = http_context

    project = make_project()
    use_case = GetProjectDetail(FakeRepository(project))

    app.dependency_overrides[
        get_authenticated_project_user
    ] = lambda: AuthenticatedProjectUser(
        user_id=USER_B,
        role=UserRole.FREELANCER,
    )

    app.dependency_overrides[
        get_project_detail_use_case
    ] = lambda: use_case

    response = client.get(f"/projects/{project.id}")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == project.id
    assert response.json()["data"]["title"] == "Website UMKM"


def test_private_project_returns_404(http_context):
    app, client = http_context

    project = make_project(published=False)
    use_case = GetProjectDetail(FakeRepository(project))

    app.dependency_overrides[
        get_authenticated_project_user
    ] = lambda: AuthenticatedProjectUser(
        user_id=USER_B,
        role=UserRole.FREELANCER,
    )

    app.dependency_overrides[
        get_project_detail_use_case
    ] = lambda: use_case

    response = client.get(f"/projects/{project.id}")

    assert response.status_code == 404
    assert response.json()["message"] == "Proyek tidak ditemukan"


def test_mine_route_not_captured_as_project_id(http_context):
    app, client = http_context

    paths = [
        route.path
        for route in app.routes
        if route.path.startswith("/projects")
    ]

    assert paths.index("/projects/mine") < paths.index(
        "/projects/{project_id}"
    )