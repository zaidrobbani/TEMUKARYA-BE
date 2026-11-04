
from datetime import date, datetime, timezone

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_handlers import (
    register_error_handlers,
)

from app.modules.admin_statistics.domain.entities import (
    AdminActor,
    AdminFreelancerProfile,
    AdminProjectDetail,
    AdminProjectSummary,
    AdminSystemStatistics,
    AdminUMKMProfile,
    AdminUserDetail,
    AdminUserSummary,
)

from app.modules.admin_statistics.presentation.dependencies import (
    get_admin_statistics_repository,
    get_authenticated_admin_actor,
)

from app.modules.admin_statistics.presentation.router import (
    router,
)


# ============================================================
# 1. TEST CONSTANTS
# ============================================================

NOW = datetime(
    2026, 11, 4, 10, 0,
    tzinfo=timezone.utc,
)

DEADLINE = date(
    2026, 12, 1
)

ADMIN = AdminActor(
    user_id="admin1",
    role="admin",
)

UMKM = AdminActor(
    user_id="u1",
    role="umkm",
)

FREELANCER = AdminActor(
    user_id="f1",
    role="freelancer",
)

USERS_URL = "/admin/users"
PROJECTS_URL = "/admin/projects"
STATISTICS_URL = "/admin/statistics"


# ============================================================
# 2. FAKE ADMIN REPOSITORY
# ============================================================

class FakeAdminRepository:
    """
    Repository simulasi untuk HTTP testing.

    Semua operasi bersifat read-only.
    Tidak memakai MySQL.
    """

    def __init__(self):

        self.calls = []

        self.users = (
            AdminUserSummary(
                id="u1",
                name="UMKM Satu",
                email="umkm@example.com",
                role="umkm",
                created_at=NOW,
            ),
            AdminUserSummary(
                id="f1",
                name="Freelancer Satu",
                email="freelancer@example.com",
                role="freelancer",
                created_at=NOW,
            ),
            AdminUserSummary(
                id="admin1",
                name="Admin Satu",
                email="admin@example.com",
                role="admin",
                created_at=NOW,
            ),
        )

        self.projects = (
            AdminProjectSummary(
                id="p1",
                title="Website UMKM",
                category_id="technology",
                umkm_id="u1",
                umkm_name="UMKM Satu",
                assigned_freelancer_id=None,
                assigned_freelancer_name=None,
                budget=2000000,
                deadline=DEADLINE,
                status="TERBUKA",
                created_at=NOW,
            ),
            AdminProjectSummary(
                id="p2",
                title="Desain Logo",
                category_id="design",
                umkm_id="u1",
                umkm_name="UMKM Satu",
                assigned_freelancer_id="f1",
                assigned_freelancer_name="Freelancer Satu",
                budget=500000,
                deadline=DEADLINE,
                status="SELESAI",
                created_at=NOW,
            ),
        )

        self.statistics = AdminSystemStatistics(
            total_umkm=1,
            total_freelancers=1,
            total_projects=2,
            completed_projects=1,
            total_transactions=3,
            platform_income=25000,
        )

    # ========================================================
    # A. FILTER USERS
    # ========================================================

    def _filter_users(
        self,
        *,
        role,
        search,
    ):
        items = list(self.users)

        if role is not None:
            items = [
                user
                for user in items
                if user.role.lower() == role.lower()
            ]

        if search is not None:
            keyword = search.casefold()

            items = [
                user
                for user in items
                if (
                    keyword in user.name.casefold()
                    or keyword in user.email.casefold()
                )
            ]

        return tuple(items)

    # ========================================================
    # B. LIST USERS
    # ========================================================

    def list_users(
        self,
        *,
        role,
        search,
        limit,
        offset,
    ):
        self.calls.append("list_users")

        items = self._filter_users(
            role=role,
            search=search,
        )

        return items[offset:offset + limit]

    # ========================================================
    # C. COUNT USERS
    # ========================================================

    def count_users(
        self,
        *,
        role,
        search,
    ):
        self.calls.append("count_users")

        return len(
            self._filter_users(
                role=role,
                search=search,
            )
        )

    # ========================================================
    # D. GET USER DETAIL
    # ========================================================

    def get_user_detail(
        self,
        user_id,
    ):
        self.calls.append("get_user_detail")

        user = next(
            (
                item
                for item in self.users
                if item.id == user_id
            ),
            None,
        )

        if user is None:
            return None

        if user.role == "umkm":
            return AdminUserDetail(
                user=user,
                umkm_profile=AdminUMKMProfile(
                    business_name="UMKM Digital",
                    business_category="Technology",
                    business_address="Malang",
                    city="Malang",
                ),
            )

        if user.role == "freelancer":
            return AdminUserDetail(
                user=user,
                freelancer_profile=(
                    AdminFreelancerProfile(
                        professional_title="Designer",
                        bio="Freelance designer",
                        city="Malang",
                        service_price_min=100000,
                        service_price_max=1000000,
                        availability_status="AVAILABLE",
                    )
                ),
            )

        return AdminUserDetail(
            user=user
        )

    # ========================================================
    # E. FILTER PROJECTS
    # ========================================================

    def _filter_projects(
        self,
        *,
        status,
        search,
    ):
        items = list(self.projects)

        if status is not None:
            items = [
                project
                for project in items
                if project.status.upper() == status.upper()
            ]

        if search is not None:
            keyword = search.casefold()

            items = [
                project
                for project in items
                if keyword in project.title.casefold()
            ]

        return tuple(items)

    # ========================================================
    # F. LIST PROJECTS
    # ========================================================

    def list_projects(
        self,
        *,
        status,
        search,
        limit,
        offset,
    ):
        self.calls.append("list_projects")

        items = self._filter_projects(
            status=status,
            search=search,
        )

        return items[offset:offset + limit]

    # ========================================================
    # G. COUNT PROJECTS
    # ========================================================

    def count_projects(
        self,
        *,
        status,
        search,
    ):
        self.calls.append("count_projects")

        return len(
            self._filter_projects(
                status=status,
                search=search,
            )
        )

    # ========================================================
    # H. GET PROJECT DETAIL
    # ========================================================

    def get_project_detail(
        self,
        project_id,
    ):
        self.calls.append("get_project_detail")

        project = next(
            (
                item
                for item in self.projects
                if item.id == project_id
            ),
            None,
        )

        if project is None:
            return None

        return AdminProjectDetail(
            project=project,
            description=(
                "Membuat website UMKM"
                if project.id == "p1"
                else "Mendesain logo bisnis"
            ),
            agreed_price=(
                None
                if project.id == "p1"
                else 450000
            ),
            published_at=NOW,
            started_at=(
                None
                if project.id == "p1"
                else NOW
            ),
            completed_at=(
                NOW
                if project.id == "p2"
                else None
            ),
        )

    # ========================================================
    # I. GET SYSTEM STATISTICS
    # ========================================================

    def get_system_statistics(self):
        self.calls.append(
            "get_system_statistics"
        )

        return self.statistics


# ============================================================
# 3. FASTAPI TEST FIXTURE
# ============================================================

@pytest.fixture
def http_context():
    """
    Membuat FastAPI khusus unit test.

    Dependency repository diganti dengan Fake.
    JWT tetap fail-closed kecuali
    secara eksplisit di-override dalam test.
    """

    app = FastAPI()

    register_error_handlers(app)

    app.include_router(router)

    repo = FakeAdminRepository()

    app.dependency_overrides[
        get_admin_statistics_repository
    ] = lambda: repo

    with TestClient(app) as client:
        yield app, client, repo

    app.dependency_overrides.clear()


# ============================================================
# 4. AUTHORIZATION TEST HELPER
# ============================================================

def authorize(
    app: FastAPI,
    actor: AdminActor,
):
    """
    Override authentication hanya untuk test.

    Jangan dipakai dalam kode production.
    """

    app.dependency_overrides[
        get_authenticated_admin_actor
    ] = lambda: actor


# ============================================================
# 5. UNAUTHENTICATED REQUESTS
# ============================================================

@pytest.mark.parametrize(
    "url",
    [
        USERS_URL,
        "/admin/users/u1",
        PROJECTS_URL,
        "/admin/projects/p1",
        STATISTICS_URL,
    ],
)
def test_unauthenticated_returns_401(
    http_context,
    url,
):
    _, client, repo = http_context

    response = client.get(url)

    assert response.status_code == 401
    assert repo.calls == []


# ============================================================
# 6. FAKE TOKEN CANNOT BYPASS AUTH
# ============================================================

def test_fake_bearer_token_rejected(
    http_context,
):
    _, client, repo = http_context

    response = client.get(
        STATISTICS_URL,
        headers={
            "Authorization": "Bearer fake-token"
        },
    )

    assert response.status_code == 401
    assert repo.calls == []


# ============================================================
# 7. FORGED ROLE HEADER CANNOT BYPASS
# ============================================================

def test_forged_role_header_rejected(
    http_context,
):
    _, client, repo = http_context

    response = client.get(
        USERS_URL,
        headers={
            "X-User-Role": "admin",
            "X-User-ID": "admin1",
        },
    )

    assert response.status_code == 401
    assert repo.calls == []


# ============================================================
# 8. NON-ADMIN AUTHORIZATION
# ============================================================

@pytest.mark.parametrize(
    "actor",
    [
        UMKM,
        FREELANCER,
    ],
)
@pytest.mark.parametrize(
    "url",
    [
        USERS_URL,
        "/admin/users/u1",
        PROJECTS_URL,
        "/admin/projects/p1",
        STATISTICS_URL,
    ],
)
def test_non_admin_returns_403(
    http_context,
    actor,
    url,
):
    app, client, repo = http_context

    authorize(
        app,
        actor,
    )

    response = client.get(
        url
    )

    assert response.status_code == 403

    # Authorization harus terjadi sebelum
    # Repository mengakses database.
    assert repo.calls == []


# ============================================================
# 9. INVALID ADMIN IDENTITY
# ============================================================

def test_invalid_admin_identity_rejected(
    http_context,
):
    app, client, repo = http_context

    authorize(
        app,
        AdminActor("", "admin"),
    )

    response = client.get(
        STATISTICS_URL
    )

    assert response.status_code == 403
    assert repo.calls == []


# ============================================================
# 10. LIST ALL USERS
# ============================================================

def test_admin_list_users(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        USERS_URL
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["limit"] == 20
    assert body["offset"] == 0


# ============================================================
# 11. FILTER USERS BY ROLE
# ============================================================

def test_admin_user_role_filter(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        USERS_URL,
        params={
            "role": "UMKM"
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert body["items"][0]["role"] == "umkm"


# ============================================================
# 12. SEARCH USERS
# ============================================================

def test_admin_user_search(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        USERS_URL,
        params={
            "search": "freelancer"
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1

    assert response.json()["items"][0]["id"] == "f1"


# ============================================================
# 13. USER PAGINATION
# ============================================================

def test_admin_user_pagination(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        USERS_URL,
        params={
            "limit": 1,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 3
    assert len(body["items"]) == 1
    assert body["offset"] == 1


# ============================================================
# 14. INVALID USER ROLE
# ============================================================

def test_invalid_user_role_filter(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        USERS_URL,
        params={
            "role": "guest"
        },
    )

    assert response.status_code == 400


# ============================================================
# 15. INVALID PAGINATION
# ============================================================

@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"offset": 10001},
    ],
)
def test_invalid_pagination_returns_422(
    http_context,
    params,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        USERS_URL,
        params=params,
    )

    assert response.status_code == 422


# ============================================================
# 16. USER DETAIL UMKM
# ============================================================

def test_admin_get_umkm_detail(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        "/admin/users/u1"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["user"]["role"] == "umkm"

    assert body["umkm_profile"]["business_name"] == (
        "UMKM Digital"
    )

    assert body["freelancer_profile"] is None


# ============================================================
# 17. USER DETAIL FREELANCER
# ============================================================

def test_admin_get_freelancer_detail(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        "/admin/users/f1"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["user"]["role"] == "freelancer"

    assert (
        body["freelancer_profile"]["professional_title"]
        == "Designer"
    )

    assert body["umkm_profile"] is None


# ============================================================
# 18. USER DETAIL ADMIN
# ============================================================

def test_admin_get_admin_user_detail(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        "/admin/users/admin1"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["user"]["role"] == "admin"

    assert body["umkm_profile"] is None
    assert body["freelancer_profile"] is None


# ============================================================
# 19. USER NOT FOUND
# ============================================================

def test_admin_user_not_found(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        "/admin/users/missing"
    )

    assert response.status_code == 404


# ============================================================
# 20. PASSWORD HASH NEVER EXPOSED
# ============================================================

def test_admin_user_response_safe(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        "/admin/users/u1"
    )

    assert response.status_code == 200

    body = response.json()

    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]

    assert "password_hash" not in response.text


# ============================================================
# 21. LIST ALL PROJECTS
# ============================================================

def test_admin_list_projects(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        PROJECTS_URL
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 2
    assert len(body["items"]) == 2

    assert (
        body["items"][0]["assigned_freelancer_id"]
        is None
    )


# ============================================================
# 22. FILTER PROJECT STATUS
# ============================================================

def test_admin_project_status_filter(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        PROJECTS_URL,
        params={
            "status": "selesai"
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 1
    assert body["items"][0]["id"] == "p2"


# ============================================================
# 23. SEARCH PROJECTS
# ============================================================

def test_admin_project_search(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        PROJECTS_URL,
        params={
            "search": "logo"
        },
    )

    assert response.status_code == 200

    assert response.json()["total"] == 1

    assert (
        response.json()["items"][0]["title"]
        == "Desain Logo"
    )


# ============================================================
# 24. PROJECT PAGINATION
# ============================================================

def test_admin_project_pagination(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        PROJECTS_URL,
        params={
            "limit": 1,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 2
    assert len(body["items"]) == 1


# ============================================================
# 25. PROJECT WITHOUT FREELANCER
# ============================================================

def test_admin_project_without_freelancer(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        "/admin/projects/p1"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["project"]["id"] == "p1"

    assert (
        body["project"]["assigned_freelancer_id"]
        is None
    )

    assert body["agreed_price"] is None


# ============================================================
# 26. PROJECT WITH FREELANCER
# ============================================================

def test_admin_project_with_freelancer(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        "/admin/projects/p2"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["project"]["id"] == "p2"

    assert (
        body["project"]["assigned_freelancer_id"]
        == "f1"
    )

    assert body["agreed_price"] == 450000


# ============================================================
# 27. PROJECT NOT FOUND
# ============================================================

def test_admin_project_not_found(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        "/admin/projects/missing"
    )

    assert response.status_code == 404


# ============================================================
# 28. INVALID PROJECT STATUS
# ============================================================

def test_invalid_project_status(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        PROJECTS_URL,
        params={
            "status": "DROP;TABLE"
        },
    )

    assert response.status_code == 400


# ============================================================
# 29. SYSTEM STATISTICS
# ============================================================

def test_admin_system_statistics(
    http_context,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.get(
        STATISTICS_URL
    )

    assert response.status_code == 200

    body = response.json()

    assert body == {
        "total_umkm": 1,
        "total_freelancers": 1,
        "total_projects": 2,
        "completed_projects": 1,
        "total_transactions": 3,
        "platform_income": 25000,
    }


# ============================================================
# 30. EMPTY SYSTEM STATISTICS
# ============================================================

def test_admin_empty_statistics(
    http_context,
):
    app, client, repo = http_context

    authorize(app, ADMIN)

    repo.statistics = AdminSystemStatistics(
        total_umkm=0,
        total_freelancers=0,
        total_projects=0,
        completed_projects=0,
        total_transactions=0,
        platform_income=0,
    )

    response = client.get(
        STATISTICS_URL
    )

    assert response.status_code == 200

    assert response.json()["total_projects"] == 0
    assert response.json()["platform_income"] == 0


# ============================================================
# 31. READ-ONLY HTTP METHODS
# ============================================================

@pytest.mark.parametrize(
    "method",
    [
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ],
)
def test_admin_users_read_only(
    http_context,
    method,
):
    app, client, _ = http_context

    authorize(app, ADMIN)

    response = client.request(
        method,
        USERS_URL,
    )

    assert response.status_code == 405


# ============================================================
# 32. OPENAPI CONTRACT
# ============================================================

def test_admin_openapi_routes(
    http_context,
):
    app, _, _ = http_context

    paths = app.openapi()["paths"]

    assert set(paths[USERS_URL]) == {
        "get"
    }

    assert set(
        paths["/admin/users/{user_id}"]
    ) == {"get"}

    assert set(paths[PROJECTS_URL]) == {
        "get"
    }

    assert set(
        paths["/admin/projects/{project_id}"]
    ) == {"get"}

    assert set(paths[STATISTICS_URL]) == {
        "get"
    }


# ============================================================
# 33. MAIN APP ROUTER REGISTRATION
# ============================================================

def test_main_app_registers_admin_router():
    """
    Memastikan router Admin terdaftar
    pada aplikasi FastAPI utama.
    """

    from app.main import app

    paths = app.openapi()["paths"]

    required = {
        "/admin/users",
        "/admin/users/{user_id}",
        "/admin/projects",
        "/admin/projects/{project_id}",
        "/admin/statistics",
    }

    assert required.issubset(
        set(paths)
    )