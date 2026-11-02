from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_handlers import register_error_handlers

from app.modules.milestones.application.dto import (
    MilestoneActor,
)

from app.modules.milestones.domain.entities import (
    Milestone,
    MilestoneStatus,
)

from app.modules.milestones.domain.repositories import (
    ProjectMilestoneContext,
)

from app.modules.milestones.presentation.dependencies import (
    get_authenticated_milestone_actor,
    get_milestone_repository,
    get_milestone_today,
)

from app.modules.milestones.presentation.router import (
    router,
)


# ============================================================
# TEST CONSTANTS
# ============================================================

PROJECT_ID = "project-1"

PLAN_URL = (
    f"/projects/{PROJECT_ID}/milestones"
)

PROGRESS_URL = (
    f"/projects/{PROJECT_ID}/milestones/progress"
)

RISK_URL = (
    f"/projects/{PROJECT_ID}/milestones/delay-risk"
)

ALL_URLS = (
    PLAN_URL,
    PROGRESS_URL,
    RISK_URL,
)

UMKM = MilestoneActor(
    user_id="umkm-1",
    role="umkm",
)

FREELANCER = MilestoneActor(
    user_id="freelancer-1",
    role="freelancer",
)


# ============================================================
# FAKE MILESTONE REPOSITORY
# ============================================================

class FakeMilestoneRepository:

    def __init__(self):

        self.project = ProjectMilestoneContext(
            project_id=PROJECT_ID,
            umkm_id=UMKM.user_id,
            freelancer_id=FREELANCER.user_id,
            status="SEDANG_DIKERJAKAN",
            started_at=datetime(2026, 11, 1),
            deadline=date(2026, 11, 11),
        )

        self.milestones = [
            Milestone(
                id="m1",
                project_id=PROJECT_ID,
                name="UI/UX",
                description="Desain UI",
                weight_percent=Decimal("20.00"),
                status=MilestoneStatus.SELESAI,
                sort_order=1,
                completed_at=datetime(2026, 11, 3),
                updated_by_user_id=FREELANCER.user_id,
            ),
            Milestone(
                id="m2",
                project_id=PROJECT_ID,
                name="Frontend",
                description="Implementasi",
                weight_percent=Decimal("30.00"),
                status=MilestoneStatus.SELESAI,
                sort_order=2,
                completed_at=datetime(2026, 11, 5),
                updated_by_user_id=FREELANCER.user_id,
            ),
            Milestone(
                id="m3",
                project_id=PROJECT_ID,
                name="Backend",
                description="API development",
                weight_percent=Decimal("50.00"),
                status=MilestoneStatus.BELUM_SELESAI,
                sort_order=3,
            ),
        ]

        self.context_calls = 0

    def get_project_context(self, project_id):

        self.context_calls += 1

        if project_id == PROJECT_ID:
            return self.project

        return None

    def list_milestones(self, project_id):

        if project_id == PROJECT_ID:
            return tuple(self.milestones)

        return ()

    def get_total_weight(self, project_id):

        if project_id != PROJECT_ID:
            return Decimal("0.00")

        return sum(
            (
                item.weight_percent
                for item in self.milestones
            ),
            Decimal("0.00"),
        )

    def replace_plan_and_reset_approvals(
        self,
        project_id,
        milestones,
    ):
        raise AssertionError(
            "Write operation must not be called"
        )

    def complete_if_pending(
        self,
        project_id,
        milestone_id,
        updated_by_user_id,
        completed_at,
    ):
        raise AssertionError(
            "Write operation must not be called"
        )


# ============================================================
# FIXTURE: HTTP TEST APPLICATION
# ============================================================

@pytest.fixture
def http_context():

    app = FastAPI()

    register_error_handlers(app)
    app.include_router(router)

    repository = FakeMilestoneRepository()

    # Repository dan tanggal boleh diganti
    # untuk test. Autentikasi tetap fail-closed
    # sampai test secara eksplisit menggantinya.

    app.dependency_overrides[
        get_milestone_repository
    ] = lambda: repository

    app.dependency_overrides[
        get_milestone_today
    ] = lambda: date(2026, 11, 8)

    with TestClient(app) as client:
        yield app, client, repository

    app.dependency_overrides.clear()


def authorize(app, actor):
    """
    Simulasi identitas yang sudah diverifikasi.

    HANYA UNTUK TEST.
    """

    app.dependency_overrides[
        get_authenticated_milestone_actor
    ] = lambda: actor


# ============================================================
# 1. AUTHENTICATION TESTS
# ============================================================

@pytest.mark.parametrize("url", ALL_URLS)
def test_unauthenticated_request_returns_401(
    http_context,
    url,
):
    _, client, _ = http_context

    response = client.get(url)

    assert response.status_code == 401


def test_fake_bearer_token_cannot_bypass_auth(
    http_context,
):
    _, client, repository = http_context

    response = client.get(
        PLAN_URL,
        headers={
            "Authorization": "Bearer fake-token",
        },
    )

    assert response.status_code == 401

    # Repository belum perlu membaca project.
    assert repository.context_calls == 0


# ============================================================
# 2. PLAN ENDPOINT TESTS
# ============================================================

def test_umkm_can_get_own_plan(http_context):
    app, client, _ = http_context

    authorize(app, UMKM)

    response = client.get(PLAN_URL)

    assert response.status_code == 200

    body = response.json()

    assert body["project_id"] == PROJECT_ID
    assert body["total_weight"] == "100.00"
    assert body["is_plan_complete"] is True

    assert len(body["items"]) == 3

    assert body["items"][0]["name"] == "UI/UX"
    assert body["items"][0]["weight_percent"] == (
        "20.00"
    )

    assert body["items"][2]["status"] == (
        "BELUM_SELESAI"
    )


def test_assigned_freelancer_can_read_plan(
    http_context,
):
    app, client, _ = http_context

    authorize(app, FREELANCER)

    response = client.get(PLAN_URL)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 3


def test_outside_umkm_cannot_read_plan(
    http_context,
):
    app, client, _ = http_context

    authorize(
        app,
        MilestoneActor(
            user_id="other-umkm",
            role="umkm",
        ),
    )

    response = client.get(PLAN_URL)

    assert response.status_code == 404


def test_unassigned_freelancer_cannot_read_plan(
    http_context,
):
    app, client, _ = http_context

    authorize(
        app,
        MilestoneActor(
            user_id="other-freelancer",
            role="freelancer",
        ),
    )

    response = client.get(PLAN_URL)

    assert response.status_code == 404


def test_invalid_role_rejected(http_context):
    app, client, _ = http_context

    authorize(
        app,
        MilestoneActor(
            user_id="admin-1",
            role="admin",
        ),
    )

    response = client.get(PLAN_URL)

    assert response.status_code == 403


def test_missing_project_returns_404(http_context):
    app, client, _ = http_context

    authorize(app, UMKM)

    response = client.get(
        "/projects/does-not-exist/milestones"
    )

    assert response.status_code == 404


def test_empty_project_id_returns_400(
    http_context,
):
    app, client, _ = http_context

    authorize(app, UMKM)

    response = client.get(
        "/projects/%20/milestones"
    )

    assert response.status_code == 400


def test_empty_milestone_plan(http_context):
    app, client, repository = http_context

    authorize(app, UMKM)

    repository.milestones = []

    response = client.get(PLAN_URL)

    assert response.status_code == 200

    body = response.json()

    assert body["items"] == []
    assert body["total_weight"] == "0.00"
    assert body["is_plan_complete"] is False


def test_corrupted_plan_returns_409(
    http_context,
):
    app, client, repository = http_context

    authorize(app, UMKM)

    repository.milestones.append(
        replace(
            repository.milestones[2],
            id="m4",
            sort_order=4,
            weight_percent=Decimal("90.00"),
        )
    )

    response = client.get(PLAN_URL)

    assert response.status_code == 409


# ============================================================
# 3. PROGRESS ENDPOINT TESTS
# ============================================================

def test_progress_returns_weighted_values(
    http_context,
):
    app, client, _ = http_context

    authorize(app, UMKM)

    response = client.get(PROGRESS_URL)

    assert response.status_code == 200

    body = response.json()

    assert body["total_weight"] == "100.00"
    assert body["completed_weight"] == "50.00"
    assert body["remaining_weight"] == "50.00"
    assert body["unallocated_weight"] == "0.00"
    assert body["progress_percent"] == "50.00"

    assert body["total_milestones"] == 3
    assert body["completed_milestones"] == 2
    assert body["is_plan_complete"] is True


def test_outsider_cannot_read_progress(
    http_context,
):
    app, client, _ = http_context

    authorize(
        app,
        MilestoneActor(
            user_id="another-umkm",
            role="umkm",
        ),
    )

    response = client.get(PROGRESS_URL)

    assert response.status_code == 404


# ============================================================
# 4. DELAY RISK ENDPOINT TESTS
# ============================================================

def test_delay_risk_at_risk(http_context):
    app, client, _ = http_context

    authorize(app, UMKM)

    response = client.get(RISK_URL)

    assert response.status_code == 200

    body = response.json()

    assert body["risk_level"] == "AT_RISK"
    assert body["expected_progress_percent"] == (
        "70.00"
    )
    assert body["actual_progress_percent"] == (
        "50.00"
    )
    assert body["gap_percent"] == "20.00"


def test_delay_risk_overdue(http_context):
    app, client, _ = http_context

    authorize(app, UMKM)

    app.dependency_overrides[
        get_milestone_today
    ] = lambda: date(2026, 11, 12)

    response = client.get(RISK_URL)

    assert response.status_code == 200
    assert response.json()["risk_level"] == "OVERDUE"


def test_delay_risk_completed(http_context):
    app, client, repository = http_context

    authorize(app, UMKM)

    repository.milestones[2] = replace(
        repository.milestones[2],
        status=MilestoneStatus.SELESAI,
        completed_at=datetime(2026, 11, 8),
    )

    response = client.get(RISK_URL)

    assert response.status_code == 200
    assert response.json()["risk_level"] == (
        "COMPLETED"
    )


def test_outsider_cannot_read_delay_risk(
    http_context,
):
    app, client, _ = http_context

    authorize(
        app,
        MilestoneActor(
            user_id="other-freelancer",
            role="freelancer",
        ),
    )

    response = client.get(RISK_URL)

    assert response.status_code == 404


# ============================================================
# 5. WRITE ENDPOINT SECURITY
# ============================================================

@pytest.mark.parametrize(
    "method",
    ["POST", "PUT", "PATCH", "DELETE"],
)
def test_write_endpoints_not_exposed(
    http_context,
    method,
):
    _, client, _ = http_context

    response = client.request(
        method,
        PLAN_URL,
    )

    assert response.status_code == 405


# ============================================================
# 6. OPENAPI CONTRACT
# ============================================================

def test_openapi_contains_three_read_routes(
    http_context,
):
    app, _, _ = http_context

    paths = app.openapi()["paths"]

    for url in ALL_URLS:
        assert url.replace(
            PROJECT_ID,
            "{project_id}",
        ) in paths

    milestone_routes = [
        path
        for path in paths
        if "/milestones" in path
    ]

    assert len(milestone_routes) == 3

    for path in milestone_routes:
        assert set(paths[path]) == {"get"}


def test_main_app_registers_milestones_router():
    """
    Memastikan router juga didaftarkan
    pada aplikasi FastAPI sesungguhnya.
    """

    from app.main import app

    paths = app.openapi()["paths"]

    assert (
        "/projects/{project_id}/milestones"
        in paths
    )

    assert (
        "/projects/{project_id}/milestones/progress"
        in paths
    )

    assert (
        "/projects/{project_id}/milestones/delay-risk"
        in paths
    )