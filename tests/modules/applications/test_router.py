
from datetime import datetime
from uuid import uuid4

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_handlers import register_error_handlers
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)

from app.modules.users.domain.entities import UserRole

from app.modules.applications.application.dto import (
    ApplicationsPage,
)

from app.modules.applications.domain.entities import (
    ProjectApplication,
)

from app.modules.applications.presentation.dependencies import (
    AuthenticatedApplicationUser,
    get_authenticated_application_user,
    get_my_applications_use_case,
    get_project_applicants_use_case,
    get_submit_application_use_case,
)

from app.modules.applications.presentation.router import (
    router,
)


# ============================================================
# TEST IDENTIFIERS
# ============================================================

FREELANCER_ID = "11111111-1111-4111-8111-111111111111"
UMKM_ID = "22222222-2222-4222-8222-222222222222"
PROJECT_ID = "33333333-3333-4333-8333-333333333333"
APPLICATION_ID = "44444444-4444-4444-8444-444444444444"

SUBMIT_URL = f"/projects/{PROJECT_ID}/applications"
MINE_URL = "/applications/mine"
APPLICANTS_URL = f"/projects/{PROJECT_ID}/applications"


# ============================================================
# TEST DATA FACTORIES
# ============================================================

def make_application(
    freelancer_id=FREELANCER_ID,
    project_id=PROJECT_ID,
):
    return ProjectApplication(
        id=APPLICATION_ID,
        project_id=project_id,
        freelancer_id=freelancer_id,
        proposed_price=1500000,
        estimated_duration_days=14,
        proposal_message="Saya siap mengerjakan proyek.",
        status="SUBMITTED",
        submitted_at=datetime(2026, 11, 2, 10, 0),
        created_at=datetime(2026, 11, 2, 10, 0),
        updated_at=datetime(2026, 11, 2, 10, 0),
    )


def valid_payload():
    return {
        "proposed_price": 1500000,
        "estimated_duration_days": 14,
        "proposal_message": (
            "Saya berpengalaman membuat website UMKM."
        ),
    }


# ============================================================
# FAKE SUBMIT USE CASE
# ============================================================

class FakeSubmitApplication:

    def __init__(self):
        self.calls = []
        self.error = None

    def execute(
        self,
        freelancer_id,
        project_id,
        data,
    ):
        self.calls.append(
            {
                "freelancer_id": freelancer_id,
                "project_id": project_id,
                "data": data,
            }
        )

        if self.error is not None:
            raise self.error

        return ProjectApplication(
            id=APPLICATION_ID,
            project_id=project_id,
            freelancer_id=freelancer_id,
            proposed_price=data.proposed_price,
            estimated_duration_days=(
                data.estimated_duration_days
            ),
            proposal_message=(
                data.proposal_message.strip()
            ),
            status="SUBMITTED",
            submitted_at=datetime(2026, 11, 2, 10, 0),
        )


# ============================================================
# FAKE GET MY APPLICATIONS
# ============================================================

class FakeGetMyApplications:

    def __init__(self):
        self.calls = []
        self.error = None
        self.items = [
            make_application()
        ]
        self.has_more = False

    def execute(
        self,
        freelancer_id,
        limit=20,
        offset=0,
    ):
        self.calls.append(
            {
                "freelancer_id": freelancer_id,
                "limit": limit,
                "offset": offset,
            }
        )

        if self.error is not None:
            raise self.error

        return ApplicationsPage(
            items=tuple(self.items),
            limit=limit,
            offset=offset,
            has_more=self.has_more,
        )


# ============================================================
# FAKE GET PROJECT APPLICANTS
# ============================================================

class FakeGetProjectApplicants:

    def __init__(self):
        self.calls = []
        self.error = None
        self.items = [
            make_application()
        ]
        self.has_more = False

    def execute(
        self,
        umkm_id,
        project_id,
        limit=20,
        offset=0,
    ):
        self.calls.append(
            {
                "umkm_id": umkm_id,
                "project_id": project_id,
                "limit": limit,
                "offset": offset,
            }
        )

        if self.error is not None:
            raise self.error

        return ApplicationsPage(
            items=tuple(self.items),
            limit=limit,
            offset=offset,
            has_more=self.has_more,
        )


# ============================================================
# FASTAPI TEST FIXTURE
# ============================================================

@pytest.fixture
def context():
    """
    Membuat aplikasi FastAPI sementara.

    Tidak menggunakan MySQL sungguhan.
    Tidak mengubah app/main.py.
    """

    app = FastAPI()

    register_error_handlers(app)
    app.include_router(router)

    submit = FakeSubmitApplication()
    mine = FakeGetMyApplications()
    applicants = FakeGetProjectApplicants()

    app.dependency_overrides[
        get_submit_application_use_case
    ] = lambda: submit

    app.dependency_overrides[
        get_my_applications_use_case
    ] = lambda: mine

    app.dependency_overrides[
        get_project_applicants_use_case
    ] = lambda: applicants

    with TestClient(app) as client:
        yield {
            "app": app,
            "client": client,
            "submit": submit,
            "mine": mine,
            "applicants": applicants,
        }

    app.dependency_overrides.clear()


# ============================================================
# AUTHENTICATION HELPER
# ============================================================

def authenticate(
    app,
    role=UserRole.FREELANCER,
    user_id=FREELANCER_ID,
):
    app.dependency_overrides[
        get_authenticated_application_user
    ] = lambda: AuthenticatedApplicationUser(
        user_id=user_id,
        role=role,
    )


# ============================================================
# 1. AUTHENTICATION REQUIRED
# ============================================================

@pytest.mark.parametrize(
    "method,url",
    [
        ("POST", SUBMIT_URL),
        ("GET", MINE_URL),
        ("GET", APPLICANTS_URL),
    ],
)
def test_endpoint_requires_authentication(
    context,
    method,
    url,
):
    client = context["client"]

    if method == "POST":
        response = client.post(
            url,
            json=valid_payload(),
        )
    else:
        response = client.get(url)

    assert response.status_code == 401

    assert context["submit"].calls == []
    assert context["mine"].calls == []
    assert context["applicants"].calls == []


# ============================================================
# 2. ROLE AUTHORIZATION
# ============================================================

@pytest.mark.parametrize(
    "method,url,role",
    [
        (
            "POST",
            SUBMIT_URL,
            UserRole.UMKM,
        ),
        (
            "GET",
            MINE_URL,
            UserRole.UMKM,
        ),
        (
            "GET",
            APPLICANTS_URL,
            UserRole.FREELANCER,
        ),
    ],
)
def test_wrong_role_returns_403(
    context,
    method,
    url,
    role,
):
    app = context["app"]
    client = context["client"]

    authenticate(
        app,
        role=role,
    )

    if method == "POST":
        response = client.post(
            url,
            json=valid_payload(),
        )
    else:
        response = client.get(url)

    assert response.status_code == 403

    assert context["submit"].calls == []
    assert context["mine"].calls == []
    assert context["applicants"].calls == []


# ============================================================
# 3. SUBMIT SUCCESS
# ============================================================

def test_submit_application_returns_201(context):
    app = context["app"]
    client = context["client"]
    submit = context["submit"]

    authenticate(app)

    response = client.post(
        SUBMIT_URL,
        json=valid_payload(),
    )

    assert response.status_code == 201

    body = response.json()["data"]

    assert body["id"] == APPLICATION_ID
    assert body["project_id"] == PROJECT_ID
    assert body["freelancer_id"] == FREELANCER_ID
    assert body["proposed_price"] == 1500000
    assert body["estimated_duration_days"] == 14
    assert body["status"] == "SUBMITTED"

    assert len(submit.calls) == 1

    call = submit.calls[0]

    assert call["freelancer_id"] == FREELANCER_ID
    assert call["project_id"] == PROJECT_ID
    assert call["data"].proposed_price == 1500000


# ============================================================
# 4. CLIENT CANNOT SPOOF FREELANCER ID
# ============================================================

def test_submit_rejects_client_freelancer_id(context):
    app = context["app"]
    client = context["client"]

    authenticate(app)

    payload = valid_payload()

    payload["freelancer_id"] = str(uuid4())

    response = client.post(
        SUBMIT_URL,
        json=payload,
    )

    assert response.status_code == 422

    assert context["submit"].calls == []


# ============================================================
# 5. REQUEST SCHEMA VALIDATION
# ============================================================

@pytest.mark.parametrize(
    "invalid_field",
    [
        {"proposed_price": 0},
        {"proposed_price": -100},
        {"proposed_price": True},
        {"proposed_price": 2**64},
        {"estimated_duration_days": 0},
        {"estimated_duration_days": True},
        {"estimated_duration_days": 2**32},
        {"proposal_message": ""},
        {"proposal_message": None},
    ],
)
def test_invalid_submit_request_returns_422(
    context,
    invalid_field,
):
    app = context["app"]
    client = context["client"]

    authenticate(app)

    payload = valid_payload()
    payload.update(invalid_field)

    response = client.post(
        SUBMIT_URL,
        json=payload,
    )

    assert response.status_code == 422

    assert context["submit"].calls == []


# ============================================================
# 6. BUSINESS VALIDATION ERROR
# ============================================================

def test_submit_business_error_returns_400(context):
    app = context["app"]
    client = context["client"]
    submit = context["submit"]

    authenticate(app)

    # Simulasikan validasi bisnis dari Application Layer,
    # misalnya pesan hanya berisi whitespace.
    submit.error = BadRequestError(
        "Pesan lamaran wajib diisi"
    )

    response = client.post(
        SUBMIT_URL,
        json={
            "proposed_price": 100000,
            "estimated_duration_days": 5,
            "proposal_message": "   ",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"success": False, "message": "Pesan lamaran wajib diisi", "data": None}


# ============================================================
# 7. DUPLICATE APPLICATION
# ============================================================

def test_duplicate_application_returns_409(context):
    app = context["app"]
    client = context["client"]
    submit = context["submit"]

    authenticate(app)

    submit.error = ConflictError(
        "Kamu sudah pernah melamar proyek ini"
    )

    response = client.post(
        SUBMIT_URL,
        json=valid_payload(),
    )

    assert response.status_code == 409


# ============================================================
# 8. PROJECT NOT AVAILABLE
# ============================================================

def test_closed_project_returns_404(context):
    app = context["app"]
    client = context["client"]
    submit = context["submit"]

    authenticate(app)

    submit.error = NotFoundError(
        "Proyek tidak tersedia untuk dilamar"
    )

    response = client.post(
        SUBMIT_URL,
        json=valid_payload(),
    )

    assert response.status_code == 404


# ============================================================
# 9. FREELANCER VIEW OWN APPLICATIONS
# ============================================================

def test_get_my_applications_returns_200(context):
    app = context["app"]
    client = context["client"]
    mine = context["mine"]

    authenticate(app)

    mine.has_more = True

    response = client.get(
        MINE_URL,
        params={
            "limit": 5,
            "offset": 0,
        },
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == "SUBMITTED"
    assert body["limit"] == 5
    assert body["offset"] == 0
    assert body["has_more"] is True

    assert mine.calls == [
        {
            "freelancer_id": FREELANCER_ID,
            "limit": 5,
            "offset": 0,
        }
    ]


# ============================================================
# 10. IDENTITY COMES FROM AUTHENTICATION
# ============================================================

def test_my_applications_uses_authenticated_identity(
    context,
):
    app = context["app"]
    client = context["client"]
    mine = context["mine"]

    another_freelancer_id = str(uuid4())

    authenticate(
        app,
        role=UserRole.FREELANCER,
        user_id=another_freelancer_id,
    )

    response = client.get(MINE_URL)

    assert response.status_code == 200

    assert mine.calls[0]["freelancer_id"] == (
        another_freelancer_id
    )


# ============================================================
# 11. UMKM VIEW PROJECT APPLICANTS
# ============================================================

def test_get_project_applicants_returns_200(context):
    app = context["app"]
    client = context["client"]
    applicants = context["applicants"]

    authenticate(
        app,
        role=UserRole.UMKM,
        user_id=UMKM_ID,
    )

    response = client.get(
        APPLICANTS_URL,
        params={
            "limit": 10,
            "offset": 0,
        },
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert len(body["items"]) == 1
    assert body["items"][0]["freelancer_id"] == (
        FREELANCER_ID
    )

    assert applicants.calls == [
        {
            "umkm_id": UMKM_ID,
            "project_id": PROJECT_ID,
            "limit": 10,
            "offset": 0,
        }
    ]


# ============================================================
# 12. FOREIGN PROJECT MUST RETURN 404
# ============================================================

def test_other_umkm_cannot_view_applicants(context):
    app = context["app"]
    client = context["client"]
    applicants = context["applicants"]

    authenticate(
        app,
        role=UserRole.UMKM,
        user_id=str(uuid4()),
    )

    # Simulasikan hasil ownership check
    # pada GetProjectApplicants.
    applicants.error = NotFoundError(
        "Proyek tidak ditemukan"
    )

    response = client.get(APPLICANTS_URL)

    assert response.status_code == 404


# ============================================================
# 13. EMPTY APPLICATION LIST
# ============================================================

def test_empty_application_list(context):
    app = context["app"]
    client = context["client"]
    mine = context["mine"]

    authenticate(app)

    mine.items = []

    response = client.get(MINE_URL)

    assert response.status_code == 200

    assert response.json()["data"]["items"] == []
    assert response.json()["data"]["has_more"] is False


# ============================================================
# 14. INVALID FREELANCER PAGINATION
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
def test_invalid_my_applications_pagination(
    context,
    params,
):
    app = context["app"]
    client = context["client"]

    authenticate(app)

    response = client.get(
        MINE_URL,
        params=params,
    )

    assert response.status_code == 422

    assert context["mine"].calls == []


# ============================================================
# 15. INVALID UMKM PAGINATION
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
def test_invalid_project_applicants_pagination(
    context,
    params,
):
    app = context["app"]
    client = context["client"]

    authenticate(
        app,
        role=UserRole.UMKM,
        user_id=UMKM_ID,
    )

    response = client.get(
        APPLICANTS_URL,
        params=params,
    )

    assert response.status_code == 422

    assert context["applicants"].calls == []