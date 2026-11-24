
from datetime import date, datetime

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_handlers import register_error_handlers

from app.modules.users.domain.entities import UserRole

from app.modules.discovery.domain.entities import (
    FreelancerDetail,
    FreelancerPortfolio,
    FreelancerReview,
    FreelancerSkill,
    FreelancerSummary,
    FreelancerWorkExperience,
)

from app.modules.discovery.presentation.router import (
    router,
)

from app.modules.discovery.presentation.dependencies import (
    AuthenticatedDiscoveryUser,
    get_authenticated_discovery_user,
    get_discovery_repository,
)


# ============================================================
# TEST CONSTANTS
# ============================================================

FREELANCER_ID = (
    "11111111-1111-4111-8111-111111111111"
)


# ============================================================
# TEST DATA
# ============================================================

def make_summary(number: int) -> FreelancerSummary:
    return FreelancerSummary(
        user_id=f"freelancer-{number}",
        name=f"Freelancer {number}",
        professional_title="Backend Developer",
        city="Malang",
        availability_status="AVAILABLE",
        service_price_min=500000,
        service_price_max=2000000,
        skills=(
            FreelancerSkill(
                id="python",
                name="Python",
            ),
        ),
        experience_count=2,
        average_rating=4.5,
        review_count=2,
    )


def make_detail() -> FreelancerDetail:
    return FreelancerDetail(
        user_id=FREELANCER_ID,
        name="Andi",
        professional_title="Backend Developer",
        city="Malang",
        availability_status="AVAILABLE",
        service_price_min=500000,
        service_price_max=2000000,
        skills=(
            FreelancerSkill(
                id="python",
                name="Python",
            ),
        ),
        experience_count=1,
        average_rating=5.0,
        review_count=1,
        bio="Saya seorang Backend Developer.",
        experiences=(
            FreelancerWorkExperience(
                id="experience-1",
                job_title="Backend Developer",
                organization_name="Tech Company",
                description="Mengembangkan API.",
                start_date=date(2024, 1, 1),
                end_date=None,
            ),
        ),
        portfolios=(
            FreelancerPortfolio(
                id="portfolio-1",
                title="Website UMKM",
                description="Website toko online.",
                project_url="https://example.com",
            ),
        ),
        reviews=(
            FreelancerReview(
                id="review-1",
                project_id="project-1",
                rating=5,
                review_text="Pekerjaannya bagus.",
                created_at=datetime(2026, 11, 2),
            ),
        ),
    )


# ============================================================
# FAKE REPOSITORY
# ============================================================

class FakeDiscoveryRepository:
    """
    Fake Repository untuk pengujian HTTP.

    Tidak terhubung ke MySQL.

    Pengujian query database sudah dilakukan
    pada STEP 5 dan STEP 6.
    """

    def __init__(self):
        self.freelancers = [
            make_summary(1),
            make_summary(2),
            make_summary(3),
        ]

        self.detail = make_detail()

        self.last_filters = None
        self.last_limit = None
        self.last_offset = None
        self.last_detail_id = None

        self.search_calls = 0
        self.detail_calls = 0

    def search_freelancers(
        self,
        filters,
        limit,
        offset,
    ):
        self.search_calls += 1

        self.last_filters = filters
        self.last_limit = limit
        self.last_offset = offset

        return self.freelancers[
            offset:offset + limit
        ]

    def get_freelancer_detail(
        self,
        freelancer_id,
    ):
        self.detail_calls += 1
        self.last_detail_id = freelancer_id

        if freelancer_id == FREELANCER_ID:
            return self.detail

        return None


# ============================================================
# FASTAPI TEST FIXTURE
# ============================================================

@pytest.fixture
def context():
    app = FastAPI()

    register_error_handlers(app)
    app.include_router(router)

    repository = FakeDiscoveryRepository()

    # Dependency Injection Override:
    # API menggunakan Fake Repository,
    # bukan database sebenarnya.

    app.dependency_overrides[
        get_discovery_repository
    ] = lambda: repository

    # Simulasi UMKM yang sudah login.
    # Ini hanya berlaku selama pengujian.

    app.dependency_overrides[
        get_authenticated_discovery_user
    ] = lambda: AuthenticatedDiscoveryUser(
        user_id="umkm-test-1",
        role=UserRole.UMKM,
    )

    with TestClient(app) as client:
        yield client, app, repository

    app.dependency_overrides.clear()


# ============================================================
# 1. SUCCESSFUL FREELANCER LIST
# ============================================================

def test_search_freelancers_200(context):
    client, app, repository = context

    response = client.get("/freelancers")

    assert response.status_code == 200

    body = response.json()["data"]

    assert len(body["items"]) == 3
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["has_more"] is False

    assert body["items"][0]["name"] == (
        "Freelancer 1"
    )


# ============================================================
# 2. SUMMARY RESPONSE DATA
# ============================================================

def test_search_response_contains_public_fields(context):
    client, app, repository = context

    response = client.get("/freelancers")

    assert response.status_code == 200

    freelancer = response.json()["data"]["items"][0]

    assert freelancer["professional_title"] == (
        "Backend Developer"
    )

    assert freelancer["city"] == "Malang"

    assert freelancer["service_price_min"] == 500000
    assert freelancer["service_price_max"] == 2000000

    assert freelancer["skills"][0]["name"] == "Python"

    assert freelancer["average_rating"] == 4.5
    assert freelancer["review_count"] == 2


# ============================================================
# 3. SEARCH PARAMETER FORWARDING
# ============================================================

def test_search_params_forwarded_to_use_case(context):
    client, app, repository = context

    response = client.get(
        "/freelancers",
        params=[
            ("search", "backend"),
            ("skill_ids", "python"),
            ("skill_ids", "fastapi"),
            ("city", "Malang"),
            ("min_price", "500000"),
            ("max_price", "2000000"),
            ("min_experience_count", "2"),
            ("min_rating", "4.0"),
        ],
    )

    assert response.status_code == 200

    filters = repository.last_filters

    assert filters.search == "backend"
    assert filters.skill_ids == (
        "python",
        "fastapi",
    )
    assert filters.city == "Malang"
    assert filters.min_price == 500000
    assert filters.max_price == 2000000
    assert filters.min_experience_count == 2
    assert filters.min_rating == 4.0


# ============================================================
# 4. AVAILABILITY FILTER
# ============================================================

def test_default_availability_available(context):
    client, app, repository = context

    response = client.get("/freelancers")

    assert response.status_code == 200

    assert (
        repository.last_filters.availability_status
        == "AVAILABLE"
    )


def test_availability_all(context):
    client, app, repository = context

    response = client.get(
        "/freelancers",
        params={
            "availability_status": "ALL",
        },
    )

    assert response.status_code == 200

    assert (
        repository.last_filters.availability_status
        is None
    )


def test_availability_normalized(context):
    client, app, repository = context

    response = client.get(
        "/freelancers",
        params={
            "availability_status": "busy",
        },
    )

    assert response.status_code == 200

    assert (
        repository.last_filters.availability_status
        == "BUSY"
    )


# ============================================================
# 5. PAGINATION
# ============================================================

def test_search_pagination(context):
    client, app, repository = context

    response = client.get(
        "/freelancers",
        params={
            "limit": 2,
            "offset": 0,
        },
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert len(body["items"]) == 2
    assert body["has_more"] is True

    # Use Case meminta limit + 1
    assert repository.last_limit == 3


def test_search_last_page(context):
    client, app, repository = context

    response = client.get(
        "/freelancers",
        params={
            "limit": 2,
            "offset": 2,
        },
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert len(body["items"]) == 1
    assert body["has_more"] is False


# ============================================================
# 6. FREELANCER DETAIL
# ============================================================

def test_get_freelancer_detail_200(context):
    client, app, repository = context

    response = client.get(
        f"/freelancers/{FREELANCER_ID}"
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert body["user_id"] == FREELANCER_ID
    assert body["name"] == "Andi"
    assert body["bio"] == (
        "Saya seorang Backend Developer."
    )

    assert len(body["skills"]) == 1
    assert len(body["experiences"]) == 1
    assert len(body["portfolios"]) == 1
    assert len(body["reviews"]) == 1

    assert body["reviews"][0]["rating"] == 5


def test_detail_serializes_dates(context):
    client, app, repository = context

    response = client.get(
        f"/freelancers/{FREELANCER_ID}"
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert (
        body["experiences"][0]["start_date"]
        == "2024-01-01"
    )

    assert (
        body["reviews"][0]["created_at"]
        == "2026-11-02T00:00:00.000Z"
    )


# ============================================================
# 7. NOT FOUND — 404
# ============================================================

def test_get_unknown_freelancer_404(context):
    client, app, repository = context

    response = client.get(
        "/freelancers/non-existent"
    )

    assert response.status_code == 404
    assert response.json() == {"success": False, "message": "Profil Freelancer tidak ditemukan", "data": None}


# ============================================================
# 8. UNAUTHENTICATED — 401
# ============================================================

@pytest.mark.parametrize(
    "path",
    [
        "/freelancers",
        f"/freelancers/{FREELANCER_ID}",
    ],
)
def test_unauthenticated_returns_401(
    context,
    path,
):
    client, app, repository = context

    # Hilangkan simulasi user login.
    # Auth asli masih fail-closed.

    app.dependency_overrides.pop(
        get_authenticated_discovery_user,
        None,
    )

    response = client.get(path)

    assert response.status_code == 401


# ============================================================
# 9. WRONG ROLE — 403
# ============================================================

@pytest.mark.parametrize(
    "path",
    [
        "/freelancers",
        f"/freelancers/{FREELANCER_ID}",
    ],
)
def test_freelancer_role_forbidden(
    context,
    path,
):
    client, app, repository = context

    app.dependency_overrides[
        get_authenticated_discovery_user
    ] = lambda: AuthenticatedDiscoveryUser(
        user_id="freelancer-test",
        role=UserRole.FREELANCER,
    )

    response = client.get(path)

    assert response.status_code == 403


def test_wrong_role_does_not_query_repository(context):
    client, app, repository = context

    app.dependency_overrides[
        get_authenticated_discovery_user
    ] = lambda: AuthenticatedDiscoveryUser(
        user_id="freelancer-test",
        role=UserRole.FREELANCER,
    )

    response = client.get("/freelancers")

    assert response.status_code == 403
    assert repository.search_calls == 0


# ============================================================
# 10. INVALID QUERY PARAMETERS — 422
# ============================================================

@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"offset": 10001},
        {"min_price": -1},
        {"max_price": -1},
        {"min_experience_count": -1},
        {"min_rating": 6},
        {"search": "x" * 101},
        {"city": "x" * 101},
    ],
)
def test_invalid_query_returns_422(
    context,
    params,
):
    client, app, repository = context

    response = client.get(
        "/freelancers",
        params=params,
    )

    assert response.status_code == 422


# ============================================================
# 11. BUSINESS VALIDATION — 400
# ============================================================

@pytest.mark.parametrize(
    "params",
    [
        {"availability_status": "INVALID"},
        {"availability_status": "   "},
        {
            "min_price": 2000000,
            "max_price": 500000,
        },
        {"search": "   "},
        {"city": "   "},
        {"skill_ids": ""},
    ],
)
def test_invalid_business_filters_return_400(
    context,
    params,
):
    client, app, repository = context

    response = client.get(
        "/freelancers",
        params=params,
    )

    assert response.status_code == 400


# ============================================================
# 12. INVALID FREELANCER ID
# ============================================================

def test_invalid_freelancer_id_returns_400(context):
    client, app, repository = context

    response = client.get(
        "/freelancers/" + ("x" * 37)
    )

    assert response.status_code == 400


# ============================================================
# 13. DATA LEAK PREVENTION
# ============================================================

@pytest.mark.parametrize(
    "path",
    [
        "/freelancers",
        f"/freelancers/{FREELANCER_ID}",
    ],
)
def test_sensitive_fields_not_exposed(
    context,
    path,
):
    client, app, repository = context

    response = client.get(path)

    assert response.status_code == 200

    response_text = response.text.lower()

    assert "password_hash" not in response_text
    assert '"password"' not in response_text
    assert '"email"' not in response_text
    assert "access_token" not in response_text


# ============================================================
# 14. OPENAPI DOCUMENTATION
# ============================================================

def test_discovery_openapi(context):
    client, app, repository = context

    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert "/freelancers" in paths
    assert "/freelancers/{freelancer_id}" in paths

    assert "get" in paths["/freelancers"]

    assert (
        "get"
        in paths["/freelancers/{freelancer_id}"]
    )