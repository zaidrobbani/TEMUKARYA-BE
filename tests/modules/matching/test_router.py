
from dataclasses import replace

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_handlers import register_error_handlers

from app.modules.users.domain.entities import UserRole

from app.modules.matching.domain.entities import (
    FreelancerMatchingSource,
    ProjectMatchingSource,
)

from app.modules.matching.presentation.dependencies import (
    AuthenticatedMatchingUser,
    get_authenticated_matching_user,
    get_matching_repository,
)

from app.modules.matching.presentation.router import router


# ============================================================
# TEST CONSTANTS
# ============================================================

UMKM_ID = "umkm-1"
FREELANCER_ID = "freelancer-1"
PROJECT_ID = "project-1"

FREELANCER_URL = (
    f"/projects/{PROJECT_ID}/recommendations/freelancers"
)

PROJECT_URL = (
    "/freelancers/me/recommendations/projects"
)

SKILLS = (
    "python",
    "fastapi",
    "mysql",
    "docker",
    "react",
)


# ============================================================
# TEST DATA FACTORIES
# ============================================================

def make_project(
    project_id=PROJECT_ID,
    owner=UMKM_ID,
    title="Website UMKM",
    skills=SKILLS,
    status="TERBUKA",
):
    return ProjectMatchingSource(
        project_id=project_id,
        umkm_id=owner,
        title=title,
        category_id="website",
        status=status,
        required_skill_ids=skills,
    )


def make_freelancer(
    freelancer_id=FREELANCER_ID,
    name="Andi",
    skills=SKILLS,
    availability="AVAILABLE",
):
    return FreelancerMatchingSource(
        freelancer_id=freelancer_id,
        name=name,
        professional_title="Backend Developer",
        city="Malang",
        availability_status=availability,
        skill_ids=skills,
        service_price_min=500000,
        service_price_max=2000000,
    )


# ============================================================
# FAKE MATCHING REPOSITORY
# ============================================================

class FakeMatchingRepository:
    """
    Fake Repository untuk pengujian HTTP.

    Tidak menggunakan MySQL.
    """

    def __init__(self):

        self.projects = {
            PROJECT_ID: make_project(),
        }

        self.freelancers = {
            FREELANCER_ID: make_freelancer(),
        }

        self.freelancer_candidates = [
            make_freelancer(
                "freelancer-2",
                "Budi",
                SKILLS[:3],
            ),
            make_freelancer(
                FREELANCER_ID,
                "Andi",
                SKILLS,
            ),
            make_freelancer(
                "freelancer-3",
                "Cici",
                SKILLS[:2],
            ),
            make_freelancer(
                "freelancer-4",
                "Dina",
                SKILLS,
                "BUSY",
            ),
        ]

        self.project_candidates = [
            make_project(
                "project-2",
                title="Backend API",
                skills=SKILLS[:3],
            ),
            make_project(
                PROJECT_ID,
                title="Website UMKM",
                skills=SKILLS,
            ),
            make_project(
                "project-3",
                title="Small API",
                skills=SKILLS[:2],
            ),
            make_project(
                "project-4",
                title="Closed Project",
                status="SELESAI",
            ),
            make_project(
                "project-5",
                title="Empty Skills",
                skills=(),
            ),
        ]

        self.project_reads = 0
        self.freelancer_reads = 0
        self.freelancer_candidate_reads = 0
        self.project_candidate_reads = 0

        self.last_project_id = None
        self.last_freelancer_id = None

    def get_project(self, project_id):
        self.project_reads += 1
        self.last_project_id = project_id
        return self.projects.get(project_id)

    def get_freelancer(self, freelancer_id):
        self.freelancer_reads += 1
        self.last_freelancer_id = freelancer_id
        return self.freelancers.get(freelancer_id)

    def iter_available_freelancers(self):
        self.freelancer_candidate_reads += 1
        return list(self.freelancer_candidates)

    def iter_published_projects(self):
        self.project_candidate_reads += 1
        return list(self.project_candidates)


# ============================================================
# AUTH HELPER
# ============================================================

def authenticate(
    app,
    role,
    user_id,
):
    """
    Simulasi user terautentikasi.

    Hanya digunakan pada unit test.
    """

    app.dependency_overrides[
        get_authenticated_matching_user
    ] = lambda: AuthenticatedMatchingUser(
        user_id=user_id,
        role=role,
    )


# ============================================================
# FASTAPI TEST FIXTURE
# ============================================================

@pytest.fixture
def context():

    app = FastAPI()

    register_error_handlers(app)
    app.include_router(router)

    repository = FakeMatchingRepository()

    app.dependency_overrides[
        get_matching_repository
    ] = lambda: repository

    # Default: UMKM yang login.
    authenticate(
        app,
        UserRole.UMKM,
        UMKM_ID,
    )

    with TestClient(app) as client:
        yield client, app, repository

    app.dependency_overrides.clear()


# ============================================================
# 1. UMKM RECOMMENDATIONS - 200
# ============================================================

def test_umkm_recommendations_200(context):
    client, app, repo = context

    response = client.get(FREELANCER_URL)

    assert response.status_code == 200

    body = response.json()["data"]

    assert body["project_id"] == PROJECT_ID
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["has_more"] is False

    assert len(body["items"]) == 2

    assert [
        item["freelancer"]["freelancer_id"]
        for item in body["items"]
    ] == [
        "freelancer-1",
        "freelancer-2",
    ]

    assert [
        item["match"]["score_percent"]
        for item in body["items"]
    ] == [
        100.0,
        60.0,
    ]


# ============================================================
# 2. FREELANCER RECOMMENDATIONS - 200
# ============================================================

def test_freelancer_recommendations_200(context):
    client, app, repo = context

    authenticate(
        app,
        UserRole.FREELANCER,
        FREELANCER_ID,
    )

    response = client.get(PROJECT_URL)

    assert response.status_code == 200

    body = response.json()["data"]

    assert body["freelancer_id"] == FREELANCER_ID
    assert len(body["items"]) == 3

    assert [
        item["project"]["project_id"]
        for item in body["items"]
    ] == [
        "project-1",
        "project-2",
        "project-3",
    ]


# ============================================================
# 3. MATCHING SCORE EXPLANATION
# ============================================================

def test_matching_response_contains_score_details(
    context,
):
    client, app, repo = context

    response = client.get(FREELANCER_URL)

    assert response.status_code == 200

    match = response.json()["data"]["items"][1]["match"]

    assert match["score_percent"] == 60.0
    assert match["required_count"] == 5
    assert match["matched_count"] == 3

    assert match["matched_skill_ids"] == list(
        SKILLS[:3]
    )

    assert match["missing_skill_ids"] == list(
        SKILLS[3:]
    )

    assert match["meets_threshold"] is True


# ============================================================
# 4. PUBLIC FREELANCER FIELDS
# ============================================================

def test_freelancer_response_public_fields(context):
    client, app, repo = context

    response = client.get(FREELANCER_URL)

    freelancer = response.json()["data"]["items"][0][
        "freelancer"
    ]

    assert freelancer["name"] == "Andi"
    assert freelancer["city"] == "Malang"

    assert freelancer["professional_title"] == (
        "Backend Developer"
    )

    assert freelancer["service_price_min"] == 500000
    assert freelancer["service_price_max"] == 2000000

    assert freelancer["availability_status"] == (
        "AVAILABLE"
    )


# ============================================================
# 5. PROJECT RESPONSE FIELDS
# ============================================================

def test_project_response_public_fields(context):
    client, app, repo = context

    authenticate(
        app,
        UserRole.FREELANCER,
        FREELANCER_ID,
    )

    response = client.get(PROJECT_URL)

    project = response.json()["data"]["items"][0]["project"]

    assert project["project_id"] == PROJECT_ID
    assert project["title"] == "Website UMKM"
    assert project["category_id"] == "website"
    assert project["status"] == "TERBUKA"

    assert project["required_skill_ids"] == list(
        SKILLS
    )


# ============================================================
# 6. UMKM PAGINATION
# ============================================================

def test_umkm_pagination_first_page(context):
    client, app, repo = context

    response = client.get(
        FREELANCER_URL,
        params={
            "limit": 1,
            "offset": 0,
        },
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert len(body["items"]) == 1
    assert body["has_more"] is True
    assert body["limit"] == 1
    assert body["offset"] == 0


def test_umkm_pagination_second_page(context):
    client, app, repo = context

    response = client.get(
        FREELANCER_URL,
        params={
            "limit": 1,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert len(body["items"]) == 1
    assert body["has_more"] is False

    assert body["items"][0]["freelancer"][
        "freelancer_id"
    ] == "freelancer-2"


def test_umkm_pagination_beyond_results(context):
    client, app, repo = context

    response = client.get(
        FREELANCER_URL,
        params={"offset": 100},
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert body["items"] == []
    assert body["has_more"] is False


# ============================================================
# 7. FREELANCER PAGINATION
# ============================================================

def test_freelancer_pagination(context):
    client, app, repo = context

    authenticate(
        app,
        UserRole.FREELANCER,
        FREELANCER_ID,
    )

    response = client.get(
        PROJECT_URL,
        params={
            "limit": 2,
            "offset": 0,
        },
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert len(body["items"]) == 2
    assert body["has_more"] is True

    next_page = client.get(
        PROJECT_URL,
        params={
            "limit": 2,
            "offset": 2,
        },
    )

    assert next_page.status_code == 200
    assert len(next_page.json()["data"]["items"]) == 1
    assert next_page.json()["data"]["has_more"] is False


# ============================================================
# 8. UNAUTHENTICATED - 401
# ============================================================

@pytest.mark.parametrize(
    "url",
    [
        FREELANCER_URL,
        PROJECT_URL,
    ],
)
def test_unauthenticated_requests_401(
    context,
    url,
):
    client, app, repo = context

    app.dependency_overrides.pop(
        get_authenticated_matching_user,
        None,
    )

    response = client.get(url)

    assert response.status_code == 401
    assert response.json() == {"success": False, "message": "Silakan login terlebih dahulu", "data": None}

    assert repo.project_reads == 0
    assert repo.freelancer_reads == 0

    assert repo.freelancer_candidate_reads == 0
    assert repo.project_candidate_reads == 0


# ============================================================
# 9. WRONG ROLE - 403
# ============================================================

def test_freelancer_cannot_request_umkm_recommendations(
    context,
):
    client, app, repo = context

    authenticate(
        app,
        UserRole.FREELANCER,
        FREELANCER_ID,
    )

    response = client.get(FREELANCER_URL)

    assert response.status_code == 403

    assert repo.project_reads == 0
    assert repo.freelancer_candidate_reads == 0


def test_umkm_cannot_request_freelancer_recommendations(
    context,
):
    client, app, repo = context

    response = client.get(PROJECT_URL)

    assert response.status_code == 403

    assert repo.freelancer_reads == 0
    assert repo.project_candidate_reads == 0


# ============================================================
# 10. PROJECT NOT FOUND - 404
# ============================================================

def test_project_not_found_404(context):
    client, app, repo = context

    response = client.get(
        "/projects/unknown/recommendations/freelancers"
    )

    assert response.status_code == 404

    assert response.json()["message"] == (
        "Project tidak ditemukan"
    )

    assert repo.freelancer_candidate_reads == 0


# ============================================================
# 11. PROJECT OWNERSHIP PROTECTION - 404
# ============================================================

def test_umkm_cannot_access_another_umkm_project(
    context,
):
    client, app, repo = context

    authenticate(
        app,
        UserRole.UMKM,
        "other-umkm",
    )

    response = client.get(FREELANCER_URL)

    assert response.status_code == 404

    assert response.json()["message"] == (
        "Project tidak ditemukan"
    )

    assert repo.freelancer_candidate_reads == 0


# ============================================================
# 12. PROJECT CLOSED - 409
# ============================================================

def test_closed_project_returns_409(context):
    client, app, repo = context

    repo.projects[PROJECT_ID] = replace(
        repo.projects[PROJECT_ID],
        status="SELESAI",
    )

    response = client.get(FREELANCER_URL)

    assert response.status_code == 409

    assert repo.freelancer_candidate_reads == 0


# ============================================================
# 13. FREELANCER PROFILE NOT FOUND - 404
# ============================================================

def test_freelancer_profile_not_found_404(context):
    client, app, repo = context

    authenticate(
        app,
        UserRole.FREELANCER,
        "unknown-freelancer",
    )

    response = client.get(PROJECT_URL)

    assert response.status_code == 404

    assert response.json()["message"] == (
        "Profil Freelancer tidak ditemukan"
    )

    assert repo.project_candidate_reads == 0


# ============================================================
# 14. QUERY PARAMETER VALIDATION - 422
# ============================================================

@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"limit": -1},
        {"limit": "invalid"},
        {"offset": -1},
        {"offset": 10001},
        {"offset": "invalid"},
    ],
)
@pytest.mark.parametrize(
    "url",
    [
        FREELANCER_URL,
        PROJECT_URL,
    ],
)
def test_invalid_pagination_returns_422(
    context,
    url,
    params,
):
    client, app, repo = context

    if url == PROJECT_URL:
        authenticate(
            app,
            UserRole.FREELANCER,
            FREELANCER_ID,
        )

    response = client.get(
        url,
        params=params,
    )

    assert response.status_code == 422


# ============================================================
# 15. PROJECT ID PATH VALIDATION - 422
# ============================================================

def test_project_id_too_long_returns_422(context):
    client, app, repo = context

    response = client.get(
        "/projects/"
        + ("x" * 37)
        + "/recommendations/freelancers"
    )

    assert response.status_code == 422


# ============================================================
# 16. EMPTY RESULTS
# ============================================================

def test_empty_freelancer_recommendations(context):
    client, app, repo = context

    repo.freelancer_candidates = []

    response = client.get(FREELANCER_URL)

    assert response.status_code == 200

    body = response.json()["data"]

    assert body["items"] == []
    assert body["has_more"] is False


def test_empty_project_recommendations(context):
    client, app, repo = context

    authenticate(
        app,
        UserRole.FREELANCER,
        FREELANCER_ID,
    )

    repo.project_candidates = []

    response = client.get(PROJECT_URL)

    assert response.status_code == 200

    body = response.json()["data"]

    assert body["items"] == []
    assert body["has_more"] is False


# ============================================================
# 17. FREELANCER WITHOUT SKILLS
# ============================================================

def test_freelancer_without_skills_gets_empty_results(
    context,
):
    client, app, repo = context

    repo.freelancers[FREELANCER_ID] = replace(
        repo.freelancers[FREELANCER_ID],
        skill_ids=(),
    )

    authenticate(
        app,
        UserRole.FREELANCER,
        FREELANCER_ID,
    )

    response = client.get(PROJECT_URL)

    assert response.status_code == 200
    assert response.json()["data"]["items"] == []

    assert repo.project_candidate_reads == 0


# ============================================================
# 18. PROJECT WITHOUT REQUIRED SKILLS
# ============================================================

def test_project_without_skills_gets_empty_results(
    context,
):
    client, app, repo = context

    repo.projects[PROJECT_ID] = replace(
        repo.projects[PROJECT_ID],
        required_skill_ids=(),
    )

    response = client.get(FREELANCER_URL)

    assert response.status_code == 200
    assert response.json()["data"]["items"] == []

    assert repo.freelancer_candidate_reads == 0


# ============================================================
# 19. BUSY FREELANCER
# ============================================================

def test_busy_freelancer_can_view_project_recommendations(
    context,
):
    client, app, repo = context

    repo.freelancers[FREELANCER_ID] = replace(
        repo.freelancers[FREELANCER_ID],
        availability_status="BUSY",
    )

    authenticate(
        app,
        UserRole.FREELANCER,
        FREELANCER_ID,
    )

    response = client.get(PROJECT_URL)

    assert response.status_code == 200
    assert len(response.json()["data"]["items"]) == 3


# ============================================================
# 20. QUERY USER ID SPOOFING
# ============================================================

def test_umkm_id_cannot_be_spoofed_via_query(
    context,
):
    client, app, repo = context

    authenticate(
        app,
        UserRole.UMKM,
        "other-umkm",
    )

    response = client.get(
        FREELANCER_URL,
        params={"umkm_id": UMKM_ID},
    )

    # Query parameter cannot override JWT identity.
    assert response.status_code == 404


def test_freelancer_id_cannot_be_spoofed_via_query(
    context,
):
    client, app, repo = context

    authenticate(
        app,
        UserRole.FREELANCER,
        "unknown-freelancer",
    )

    response = client.get(
        PROJECT_URL,
        params={"freelancer_id": FREELANCER_ID},
    )

    assert response.status_code == 404


# ============================================================
# 21. SENSITIVE DATA PROTECTION
# ============================================================

@pytest.mark.parametrize(
    "url",
    [
        FREELANCER_URL,
        PROJECT_URL,
    ],
)
def test_response_has_no_sensitive_fields(
    context,
    url,
):
    client, app, repo = context

    if url == PROJECT_URL:
        authenticate(
            app,
            UserRole.FREELANCER,
            FREELANCER_ID,
        )

    response = client.get(url)

    assert response.status_code == 200

    serialized = response.text.lower()

    for forbidden in (
        "password_hash",
        "access_token",
        "refresh_token",
        "secret_password",
        "email",
    ):
        assert forbidden not in serialized


# ============================================================
# 22. OPENAPI DOCUMENTATION
# ============================================================

def test_matching_endpoints_registered_in_openapi(
    context,
):
    client, app, repo = context

    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    assert (
        "/projects/{project_id}/recommendations/freelancers"
        in paths
    )

    assert (
        "/freelancers/me/recommendations/projects"
        in paths
    )

    assert "get" in paths[
        "/projects/{project_id}/recommendations/freelancers"
    ]

    assert "get" in paths[
        "/freelancers/me/recommendations/projects"
    ]


# ============================================================
# 23. MATCHING REQUESTS ARE READ-ONLY
# ============================================================

def test_matching_only_exposes_get_routes(context):
    client, app, repo = context

    response = client.post(FREELANCER_URL)

    assert response.status_code == 405

    response = client.delete(PROJECT_URL)

    assert response.status_code == 405


# ============================================================
# 24. STABLE RECOMMENDATION ORDER
# ============================================================

def test_recommendation_order_is_deterministic(
    context,
):
    client, app, repo = context

    first = client.get(FREELANCER_URL)
    second = client.get(FREELANCER_URL)

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.json()["data"]["items"] == (
        second.json()["data"]["items"]
    )


# ============================================================
# 25. MATCHING THRESHOLD ENFORCED
# ============================================================

def test_only_eligible_matches_are_returned(
    context,
):
    client, app, repo = context

    response = client.get(FREELANCER_URL)

    assert response.status_code == 200

    for item in response.json()["data"]["items"]:
        assert item["match"]["score_percent"] >= 60
        assert item["match"]["meets_threshold"] is True


# ============================================================
# 26. PROJECT ID FORWARDED TO REPOSITORY
# ============================================================

def test_project_id_forwarded_correctly(context):
    client, app, repo = context

    response = client.get(FREELANCER_URL)

    assert response.status_code == 200
    assert repo.last_project_id == PROJECT_ID


# ============================================================
# 27. FREELANCER ID FROM AUTHENTICATION
# ============================================================

def test_freelancer_id_from_authentication(context):
    client, app, repo = context

    authenticate(
        app,
        UserRole.FREELANCER,
        FREELANCER_ID,
    )

    response = client.get(PROJECT_URL)

    assert response.status_code == 200
    assert repo.last_freelancer_id == FREELANCER_ID