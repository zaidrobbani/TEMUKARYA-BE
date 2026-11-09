
from datetime import date, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_handlers import register_error_handlers
from app.modules.users.domain.entities import UserRole

from app.modules.projects.domain.entities import Project
from app.modules.projects.presentation.router import router
from app.modules.projects.presentation.dependencies import (
    AuthenticatedProjectUser,
    get_authenticated_project_user,
    get_create_project_use_case,
)


# ============================================================
# 1. FAKE CREATE PROJECT USE CASE
# ============================================================

class FakeCreateProject:
    def __init__(self):
        self.calls = []
        self.error = None

    def execute(self, umkm_id, data):
        if self.error is not None:
            raise self.error

        self.calls.append((umkm_id, data))

        return Project(
            id=str(uuid4()),
            umkm_id=umkm_id,
            category_id=data.category_id,
            title=data.title,
            description=data.description,
            budget=data.budget,
            deadline=data.deadline,
            status="TERBUKA",
            published_at=datetime(2026, 11, 2, 10, 0, 0),
        )


# ============================================================
# 2. PYTEST FIXTURES
# ============================================================

@pytest.fixture
def valid_payload():
    return {
        "category_id": "website",
        "title": "Pembuatan Website UMKM",
        "description": "Membuat website company profile",
        "budget": 3000000,
        "deadline": "2026-12-31",
        "skill_ids": ["python", "fastapi"],
    }


@pytest.fixture
def test_context():
    app = FastAPI()

    register_error_handlers(app)
    app.include_router(router)

    fake_use_case = FakeCreateProject()

    app.dependency_overrides[
        get_create_project_use_case
    ] = lambda: fake_use_case

    with TestClient(app) as client:
        yield app, client, fake_use_case

    app.dependency_overrides.clear()


def override_as_umkm(app):
    app.dependency_overrides[
        get_authenticated_project_user
    ] = lambda: AuthenticatedProjectUser(
        user_id="11111111-1111-4111-8111-111111111111",
        role=UserRole.UMKM,
    )


def override_as_freelancer(app):
    app.dependency_overrides[
        get_authenticated_project_user
    ] = lambda: AuthenticatedProjectUser(
        user_id="22222222-2222-4222-8222-222222222222",
        role=UserRole.FREELANCER,
    )


# ============================================================
# 3. AUTHENTICATION & AUTHORIZATION TESTS
# ============================================================

def test_create_project_requires_authentication(
    test_context, valid_payload
):
    app, client, fake_use_case = test_context

    response = client.post(
        "/projects",
        json=valid_payload,
    )

    assert response.status_code == 401
    assert fake_use_case.calls == []


def test_freelancer_cannot_create_project(
    test_context, valid_payload
):
    app, client, fake_use_case = test_context

    override_as_freelancer(app)

    response = client.post(
        "/projects",
        json=valid_payload,
    )

    assert response.status_code == 403
    assert fake_use_case.calls == []


# ============================================================
# 4. SUCCESS TEST
# ============================================================

def test_umkm_can_create_project(
    test_context, valid_payload
):
    app, client, fake_use_case = test_context

    override_as_umkm(app)

    response = client.post(
        "/projects",
        json=valid_payload,
    )

    assert response.status_code == 201
    assert response.json()["message"] == "Project berhasil dibuat"

    body = response.json()["data"]

    assert body["title"] == valid_payload["title"]
    assert body["budget"] == 3000000
    assert body["status"] == "TERBUKA"
    assert body["category_id"] == "website"

    assert len(fake_use_case.calls) == 1

    passed_umkm_id, passed_data = fake_use_case.calls[0]

    assert passed_umkm_id == (
        "11111111-1111-4111-8111-111111111111"
    )

    assert passed_data.skill_ids == (
        "python",
        "fastapi",
    )


# ============================================================
# 5. VALIDATION TESTS
# ============================================================

def test_rejects_negative_budget(
    test_context, valid_payload
):
    app, client, fake_use_case = test_context

    override_as_umkm(app)

    payload = {
        **valid_payload,
        "budget": -1000,
    }

    response = client.post(
        "/projects",
        json=payload,
    )

    assert response.status_code == 422
    assert fake_use_case.calls == []


def test_rejects_client_supplied_umkm_id(
    test_context, valid_payload
):
    app, client, fake_use_case = test_context

    override_as_umkm(app)

    payload = {
        **valid_payload,
        "umkm_id": "fake-user-id",
    }

    response = client.post(
        "/projects",
        json=payload,
    )

    assert response.status_code == 422
    assert fake_use_case.calls == []


def test_handles_business_validation_error(
    test_context, valid_payload
):
    app, client, fake_use_case = test_context

    override_as_umkm(app)

    fake_use_case.error = ValueError(
        "Kategori proyek tidak valid atau tidak aktif."
    )

    response = client.post(
        "/projects",
        json=valid_payload,
    )

    assert response.status_code == 400
    assert "Kategori" in response.json()["message"]
    assert response.json()["success"] is False
    assert fake_use_case.calls == []


# ============================================================
# 6. GET MY PROJECTS TESTS
# ============================================================

from app.modules.projects.presentation.dependencies import (
    get_my_projects_use_case,
)


class FakeGetMyProjects:
    def __init__(self, projects=None):
        self.projects = projects if projects is not None else []
        self.calls = []

    def execute(self, umkm_id: str):
        self.calls.append(umkm_id)

        # Simulasi repository yang hanya mengambil
        # proyek milik UMKM terautentikasi.
        return [
            project
            for project in self.projects
            if project.umkm_id == umkm_id
        ]


def make_test_project(umkm_id: str, title: str) -> Project:
    return Project(
        id=str(uuid4()),
        umkm_id=umkm_id,
        category_id="website",
        title=title,
        description="Proyek pengujian.",
        budget=2000000,
        deadline=date(2026, 12, 31),
        status="TERBUKA",
        published_at=datetime(2026, 11, 2, 10, 0, 0),
    )


def test_get_my_projects_requires_authentication(test_context):
    app, client, _ = test_context

    fake = FakeGetMyProjects()
    app.dependency_overrides[get_my_projects_use_case] = lambda: fake

    response = client.get("/projects/mine")

    assert response.status_code == 401
    assert fake.calls == []


def test_freelancer_cannot_get_my_projects(test_context):
    app, client, _ = test_context

    override_as_freelancer(app)

    fake = FakeGetMyProjects()
    app.dependency_overrides[get_my_projects_use_case] = lambda: fake

    response = client.get("/projects/mine")

    assert response.status_code == 403
    assert fake.calls == []


def test_umkm_only_sees_own_projects(test_context):
    app, client, _ = test_context

    override_as_umkm(app)

    umkm_a = "11111111-1111-4111-8111-111111111111"
    umkm_b = "33333333-3333-4333-8333-333333333333"

    fake = FakeGetMyProjects(
        projects=[
            make_test_project(umkm_a, "Project UMKM A"),
            make_test_project(umkm_b, "Project UMKM B"),
        ]
    )

    app.dependency_overrides[get_my_projects_use_case] = lambda: fake

    response = client.get("/projects/mine")

    assert response.status_code == 200

    data = response.json()["data"]

    assert len(data) == 1
    assert data[0]["title"] == "Project UMKM A"
    assert data[0]["umkm_id"] == umkm_a
    assert fake.calls == [umkm_a]


def test_umkm_with_no_projects_gets_empty_list(test_context):
    app, client, _ = test_context

    override_as_umkm(app)

    fake = FakeGetMyProjects()
    app.dependency_overrides[get_my_projects_use_case] = lambda: fake

    response = client.get("/projects/mine")

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Daftar project berhasil diambil", "data": []}
    assert len(fake.calls) == 1


# ============================================================
# 7. UPDATE PROJECT HTTP TESTS
# ============================================================

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.projects.presentation.dependencies import (
    get_update_project_use_case,
)


UPDATE_PROJECT_ID = "33333333-3333-4333-8333-333333333333"
UPDATE_UMKM_ID = "11111111-1111-4111-8111-111111111111"


class FakeUpdateProject:
    def __init__(self):
        self.calls = []
        self.error = None

    def execute(self, umkm_id, project_id, data):
        self.calls.append((umkm_id, project_id, data))

        if self.error is not None:
            raise self.error

        return Project(
            id=project_id,
            umkm_id=umkm_id,
            category_id=data.category_id,
            title=data.title,
            description=data.description,
            budget=data.budget,
            deadline=data.deadline,
            status="TERBUKA",
            published_at=datetime(2026, 11, 2, 10, 0),
        )


def setup_update_override(app):
    fake = FakeUpdateProject()

    app.dependency_overrides[
        get_update_project_use_case
    ] = lambda: fake

    return fake


def test_update_requires_authentication(
    test_context, valid_payload
):
    app, client, _ = test_context
    fake = setup_update_override(app)

    response = client.put(
        f"/projects/{UPDATE_PROJECT_ID}",
        json=valid_payload,
    )

    assert response.status_code == 401
    assert fake.calls == []


def test_freelancer_cannot_update_project(
    test_context, valid_payload
):
    app, client, _ = test_context

    override_as_freelancer(app)
    fake = setup_update_override(app)

    response = client.put(
        f"/projects/{UPDATE_PROJECT_ID}",
        json=valid_payload,
    )

    assert response.status_code == 403
    assert fake.calls == []


def test_umkm_can_update_project(
    test_context, valid_payload
):
    app, client, _ = test_context

    override_as_umkm(app)
    fake = setup_update_override(app)

    payload = {
        **valid_payload,
        "title": "Website UMKM Versi Baru",
        "budget": 4500000,
    }

    response = client.put(
        f"/projects/{UPDATE_PROJECT_ID}",
        json=payload,
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Project berhasil diperbarui"

    body = response.json()["data"]

    assert body["id"] == UPDATE_PROJECT_ID
    assert body["umkm_id"] == UPDATE_UMKM_ID
    assert body["title"] == "Website UMKM Versi Baru"
    assert body["budget"] == 4500000
    assert body["status"] == "TERBUKA"

    assert len(fake.calls) == 1

    passed_umkm_id, passed_project_id, passed_data = (
        fake.calls[0]
    )

    assert passed_umkm_id == UPDATE_UMKM_ID
    assert passed_project_id == UPDATE_PROJECT_ID
    assert passed_data.title == "Website UMKM Versi Baru"


def test_update_rejects_negative_budget_http(
    test_context, valid_payload
):
    app, client, _ = test_context

    override_as_umkm(app)
    fake = setup_update_override(app)

    response = client.put(
        f"/projects/{UPDATE_PROJECT_ID}",
        json={
            **valid_payload,
            "budget": -1000,
        },
    )

    assert response.status_code == 422
    assert fake.calls == []


def test_update_rejects_forged_umkm_id(
    test_context, valid_payload
):
    app, client, _ = test_context

    override_as_umkm(app)
    fake = setup_update_override(app)

    response = client.put(
        f"/projects/{UPDATE_PROJECT_ID}",
        json={
            **valid_payload,
            "umkm_id": "fake-umkm-id",
        },
    )

    assert response.status_code == 422
    assert fake.calls == []


def test_update_handles_business_validation_error(
    test_context, valid_payload
):
    app, client, _ = test_context

    override_as_umkm(app)
    fake = setup_update_override(app)

    fake.error = ValueError(
        "Kategori proyek tidak valid atau tidak aktif"
    )

    response = client.put(
        f"/projects/{UPDATE_PROJECT_ID}",
        json=valid_payload,
    )

    assert response.status_code == 400
    assert "Kategori" in response.json()["message"]
    assert response.json()["success"] is False


def test_update_returns_404_when_project_not_found(
    test_context, valid_payload
):
    app, client, _ = test_context

    override_as_umkm(app)
    fake = setup_update_override(app)

    fake.error = NotFoundError(
        "Proyek tidak ditemukan"
    )

    response = client.put(
        f"/projects/{UPDATE_PROJECT_ID}",
        json=valid_payload,
    )

    assert response.status_code == 404
    assert response.json()["message"] == (
        "Proyek tidak ditemukan"
    )


def test_update_returns_409_when_project_started(
    test_context, valid_payload
):
    app, client, _ = test_context

    override_as_umkm(app)
    fake = setup_update_override(app)

    fake.error = ConflictError(
        "Proyek yang sudah dimulai tidak dapat diubah"
    )

    response = client.put(
        f"/projects/{UPDATE_PROJECT_ID}",
        json=valid_payload,
    )

    assert response.status_code == 409
    assert "tidak dapat diubah" in (
        response.json()["message"]
    )