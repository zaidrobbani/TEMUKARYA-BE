
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_handlers import register_error_handlers
from app.modules.users.domain.entities import UserRole

from app.modules.projects.application.dto import PublicProjectsPage
from app.modules.projects.application.use_cases import SearchPublicProjects
from app.modules.projects.domain.entities import Project
from app.modules.projects.presentation.dependencies import (
    AuthenticatedProjectUser,
    get_authenticated_project_user,
    get_search_public_projects_use_case,
)
from app.modules.projects.presentation.router import router


FREELANCER_ID = "22222222-2222-4222-8222-222222222222"
UMKM_ID = "11111111-1111-4111-8111-111111111111"


# ============================================================
# TEST DATA
# ============================================================

def make_project(
    title="Website UMKM",
    category_id="website",
    budget=3000000,
):
    return Project(
        id=str(uuid4()),
        umkm_id=UMKM_ID,
        category_id=category_id,
        title=title,
        description=f"Deskripsi proyek {title}",
        budget=budget,
        deadline=date.today() + timedelta(days=30),
        status="TERBUKA",
        published_at=datetime(2026, 11, 2, 10, 0),
    )


# ============================================================
# FAKE REPOSITORY
# ============================================================

class FakeSearchRepository:
    def __init__(self, projects=None):
        self.projects = list(projects or [])
        self.calls = []

    def search_public(
        self,
        search,
        category_id,
        min_budget,
        max_budget,
        limit,
        offset,
    ):
        self.calls.append({
            "search": search,
            "category_id": category_id,
            "min_budget": min_budget,
            "max_budget": max_budget,
            "limit": limit,
            "offset": offset,
        })

        results = self.projects

        if search and search.strip():
            keyword = search.strip().lower()

            results = [
                project for project in results
                if keyword in project.title.lower()
                or keyword in project.description.lower()
            ]

        if category_id:
            results = [
                project for project in results
                if project.category_id == category_id
            ]

        if min_budget is not None:
            results = [
                project for project in results
                if project.budget >= min_budget
            ]

        if max_budget is not None:
            results = [
                project for project in results
                if project.budget <= max_budget
            ]

        return results[offset:offset + limit]


# ============================================================
# UNIT TESTS
# ============================================================

def test_search_public_projects_success():
    repository = FakeSearchRepository([
        make_project(title="Website UMKM"),
        make_project(title="Desain Logo"),
    ])

    use_case = SearchPublicProjects(repository)

    result = use_case.execute(
        search="website",
        limit=20,
        offset=0,
    )

    assert len(result.items) == 1
    assert result.items[0].title == "Website UMKM"
    assert result.has_more is False
    assert repository.calls[0]["search"] == "website"


def test_search_filters_category_and_budget():
    repository = FakeSearchRepository([
        make_project(
            title="Website A",
            category_id="website",
            budget=1000000,
        ),
        make_project(
            title="Website B",
            category_id="website",
            budget=4000000,
        ),
        make_project(
            title="Desain Logo",
            category_id="graphic_design",
            budget=3000000,
        ),
    ])

    use_case = SearchPublicProjects(repository)

    result = use_case.execute(
        category_id="website",
        min_budget=2000000,
        max_budget=5000000,
    )

    assert len(result.items) == 1
    assert result.items[0].title == "Website B"


def test_search_pagination_has_more():
    repository = FakeSearchRepository([
        make_project(title=f"Project {i}")
        for i in range(5)
    ])

    use_case = SearchPublicProjects(repository)

    first_page = use_case.execute(
        limit=2,
        offset=0,
    )

    assert len(first_page.items) == 2
    assert first_page.has_more is True
    assert repository.calls[0]["limit"] == 3

    last_page = use_case.execute(
        limit=2,
        offset=4,
    )

    assert len(last_page.items) == 1
    assert last_page.has_more is False


def test_search_empty_results():
    repository = FakeSearchRepository()
    use_case = SearchPublicProjects(repository)

    result = use_case.execute()

    assert result.items == ()
    assert result.has_more is False
    assert result.limit == 20
    assert result.offset == 0


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"min_budget": -1},
        {"max_budget": -1},
        {"min_budget": 5000000, "max_budget": 1000000},
    ],
)
def test_search_rejects_invalid_parameters(params):
    repository = FakeSearchRepository()
    use_case = SearchPublicProjects(repository)

    with pytest.raises(ValueError):
        use_case.execute(**params)

    assert repository.calls == []


# ============================================================
# FAKE USE CASE FOR HTTP TESTS
# ============================================================

class FakeSearchUseCase:
    def __init__(self):
        self.calls = []
        self.error = None

    def execute(self, **kwargs):
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return PublicProjectsPage(
            items=(make_project(),),
            limit=kwargs.get("limit", 20),
            offset=kwargs.get("offset", 0),
            has_more=False,
        )


@pytest.fixture
def http_context():
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)

    fake = FakeSearchUseCase()

    app.dependency_overrides[
        get_search_public_projects_use_case
    ] = lambda: fake

    with TestClient(app) as client:
        yield app, client, fake

    app.dependency_overrides.clear()


def authenticate(app, role):
    app.dependency_overrides[
        get_authenticated_project_user
    ] = lambda: AuthenticatedProjectUser(
        user_id=FREELANCER_ID,
        role=role,
    )


# ============================================================
# HTTP TESTS
# ============================================================

def test_search_requires_authentication(http_context):
    app, client, fake = http_context

    response = client.get("/projects")

    assert response.status_code == 401
    assert fake.calls == []


def test_umkm_cannot_access_freelancer_search(http_context):
    app, client, fake = http_context

    authenticate(app, UserRole.UMKM)

    response = client.get("/projects")

    assert response.status_code == 403
    assert fake.calls == []


def test_freelancer_can_search_projects(http_context):
    app, client, fake = http_context

    authenticate(app, UserRole.FREELANCER)

    response = client.get(
        "/projects",
        params={
            "search": "website",
            "category_id": "website",
            "min_budget": 1000000,
            "max_budget": 5000000,
            "limit": 10,
            "offset": 0,
        },
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Website UMKM"
    assert body["limit"] == 10
    assert body["offset"] == 0
    assert body["has_more"] is False

    assert len(fake.calls) == 1
    assert fake.calls[0]["search"] == "website"
    assert fake.calls[0]["category_id"] == "website"
    assert fake.calls[0]["min_budget"] == 1000000
    assert fake.calls[0]["max_budget"] == 5000000


def test_search_rejects_invalid_query_limit(http_context):
    app, client, fake = http_context

    authenticate(app, UserRole.FREELANCER)

    response = client.get(
        "/projects",
        params={"limit": 101},
    )

    assert response.status_code == 422
    assert fake.calls == []


def test_search_rejects_invalid_budget_range_http(http_context):
    app, client, fake = http_context

    authenticate(app, UserRole.FREELANCER)

    fake.error = ValueError(
        "Minimum budget tidak boleh melebihi maksimum budget"
    )

    response = client.get(
        "/projects",
        params={
            "min_budget": 5000000,
            "max_budget": 1000000,
        },
    )

    assert response.status_code == 400
    assert "budget" in response.json()["message"].lower()


def test_search_does_not_conflict_with_project_detail(http_context):
    app, client, fake = http_context

    authenticate(app, UserRole.FREELANCER)

    response = client.get("/projects")

    assert response.status_code == 200
    assert len(fake.calls) == 1