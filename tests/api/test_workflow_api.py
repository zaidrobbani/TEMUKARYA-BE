"""Test HTTP workflow, pembayaran, hasil kerja, ulasan, notifikasi, dan admin keuangan (fake repository)."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_uow
from app.main import app
from app.modules.admin_finance.presentation.router import get_admin_finance_repository
from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.milestones.presentation.dependencies import get_milestone_repository
from app.modules.notifications.presentation.dependencies import get_notification_repository
from app.modules.payments.presentation.dependencies import get_payment_repository, get_wallet_repository
from app.modules.reviews.presentation.dependencies import get_review_repository
from app.modules.submissions.presentation.dependencies import get_submission_repository, get_submission_storage
from app.modules.users.domain.entities import User, UserRole
from app.modules.workflow.presentation.dependencies import get_milestone_weight_reader
from app.modules.workflow.presentation.providers import get_workflow_repository
from tests.modules.workflow.fakes import (
    FREELANCER_ID,
    OTHER_FREELANCER_ID,
    PROJECT_ID,
    UMKM_ID,
    FakeAdminFinanceRepository,
    FakeNotificationRepository,
)
from tests.modules.workflow.test_milestone_actions import FakeRepo
from tests.modules.workflow.world import PDF, PNG, World

BASE = f"/api/v1/projects/{PROJECT_ID}"
APP_ID = f"app-{FREELANCER_ID}-{PROJECT_ID}"


def make_user(user_id: str, role: UserRole) -> User:
    return User(name=user_id, email=f"{user_id}@x.id", password_hash="-", role=role, id=user_id)


USERS = {
    "umkm": make_user(UMKM_ID, UserRole.UMKM),
    "freelancer": make_user(FREELANCER_ID, UserRole.FREELANCER),
    "other": make_user(OTHER_FREELANCER_ID, UserRole.FREELANCER),
    "admin": make_user("admin-1", UserRole.ADMIN),
}


class Api:
    def __init__(self, client: TestClient, world: World):
        self.client = client
        self.w = world
        self.as_user: str | None = "umkm"

    def call(self, method: str, path: str, user: str | None = "umkm", **kwargs):
        self.as_user = user
        return self.client.request(method, path, **kwargs)


@pytest.fixture
def api():
    world = World()
    milestone_repo = FakeRepo()
    api = None

    def current_user():
        from app.modules.auth.domain.exceptions import NotAuthenticatedError

        if api.as_user is None:
            raise NotAuthenticatedError()
        return USERS[api.as_user]

    app.dependency_overrides = {
        get_current_user: current_user,
        get_uow: lambda: world.uow,
        get_workflow_repository: lambda: world.workflow,
        get_payment_repository: lambda: world.payments,
        get_wallet_repository: lambda: world.wallets,
        get_submission_repository: lambda: world.submissions,
        get_submission_storage: lambda: world.storage,
        get_review_repository: lambda: world.reviews,
        get_notification_repository: lambda: FakeNotificationRepository(world.store),
        get_milestone_weight_reader: lambda: world.milestones,
        get_admin_finance_repository: lambda: FakeAdminFinanceRepository(world.store),
        get_milestone_repository: lambda: milestone_repo,
    }
    with TestClient(app, raise_server_exceptions=False) as client:
        api = Api(client, world)
        api.milestone_repo = milestone_repo
        yield api
    app.dependency_overrides = {}


def ok(response, status=200):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["success"] is True
    assert set(body) == {"success", "message", "data"}
    return body["data"]


def err(response, status, message=None):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["success"] is False and body["data"] is None
    if message:
        assert message in body["message"]
    return body


def select(api):
    api.w.store.add_application()
    return ok(api.call("POST", f"{BASE}/agreement", json={"application_id": APP_ID}), 201)


def finalize(api):
    select(api)
    api.w.set_plan()
    ok(api.call("POST", f"{BASE}/agreement/approve", "freelancer"))
    return ok(api.call("POST", f"{BASE}/agreement/approve", json={"agreement_version": 1}))


def to_working(api):
    finalize(api)
    ok(api.call("POST", f"{BASE}/payment/simulate", headers={"Idempotency-Key": "key-0000001"}))
    ok(api.call("POST", f"{BASE}/start", "freelancer"))


def to_review(api):
    to_working(api)
    return ok(
        api.call("POST", f"{BASE}/submissions", "freelancer", data={"result_url": "https://drive.google.com/x"}),
        201,
    )


class TestAuth:
    @pytest.mark.parametrize(
        "method, path",
        [
            ("GET", "/api/v1/workflow/projects"),
            ("GET", f"{BASE}/workflow"),
            ("POST", f"{BASE}/agreement"),
            ("POST", f"{BASE}/cancel"),
            ("GET", f"{BASE}/payment"),
            ("POST", f"{BASE}/payment/simulate"),
            ("GET", "/api/v1/payments/history"),
            ("GET", "/api/v1/wallet"),
            ("POST", f"{BASE}/submissions"),
            ("POST", f"{BASE}/review"),
            ("GET", "/api/v1/notifications"),
            ("GET", "/api/v1/admin/finance/summary"),
            ("PUT", f"{BASE}/milestones"),
        ],
    )
    def test_login_required(self, api, method, path):
        err(api.call(method, path, None), 401)

    @pytest.mark.parametrize("user", ["umkm", "freelancer"])
    def test_admin_finance_requires_admin(self, api, user):
        err(api.call("GET", "/api/v1/admin/finance/summary", user), 403)


class TestWorkflowApi:
    def test_select_and_detail_shape(self, api):
        data = select(api)
        assert data["project"]["status"] == "MENUNGGU_KESEPAKATAN"
        assert data["project"]["status_label"] == "Menunggu Kesepakatan"
        assert data["my_role"] == "UMKM"
        agreement = data["agreement"]
        assert agreement["agreed_price"] == 1_500_000
        assert agreement["duration_days"] == 14
        assert agreement["platform_fee_amount"] == 75_000
        assert agreement["freelancer_amount"] == 1_425_000
        assert agreement["payment_method_label"] == "QRIS (simulasi)"
        assert agreement["waiting_for"] == ["UMKM", "FREELANCER"]
        assert data["freelancer"]["subtitle"] == "Desainer Grafis"
        assert data["history"][0]["new_status_label"] == "Menunggu Kesepakatan"
        assert data["history"][0]["changed_at"].endswith("Z")
        assert {"action": "APPROVE_AGREEMENT", "label": "Lanjut project"} in data["available_actions"]

        freelancer_view = ok(api.call("GET", f"{BASE}/workflow", "freelancer"))
        assert freelancer_view["my_role"] == "FREELANCER"
        err(api.call("GET", f"{BASE}/workflow", "other"), 404, "Proyek tidak ditemukan")

    @pytest.mark.parametrize(
        "body",
        [{}, {"application_id": "a", "freelancer_id": "b"}, {"freelancer_id": "b", "extra": 1}],
    )
    def test_select_validation(self, api, body):
        body = err(api.call("POST", f"{BASE}/agreement", json=body), 422)
        assert body["errors"]

    def test_select_by_freelancer_role_forbidden(self, api):
        err(api.call("POST", f"{BASE}/agreement", "freelancer", json={"freelancer_id": FREELANCER_ID}), 403)

    def test_select_twice_conflict(self, api):
        select(api)
        err(api.call("POST", f"{BASE}/agreement", json={"freelancer_id": OTHER_FREELANCER_ID}), 409)

    def test_update_agreement(self, api):
        select(api)
        data = ok(api.call("PATCH", f"{BASE}/agreement", "freelancer", json={"duration_days": 10, "agreed_price": 1_600_000}))
        assert data["agreement"]["agreement_version"] == 2
        assert data["agreement"]["duration_days"] == 10
        err(api.call("PATCH", f"{BASE}/agreement", json={"agreed_price": 0}), 422)
        err(api.call("PATCH", f"{BASE}/agreement", json={"agreed_deadline": "07-11-2026"}), 422)
        err(api.call("PATCH", f"{BASE}/agreement", json={}), 400, "Tidak ada perubahan")

    def test_approve_flow_and_codes(self, api):
        select(api)
        api.w.set_plan(("50",))
        body = err(api.call("POST", f"{BASE}/agreement/approve", "freelancer"), 409)
        assert body["code"] == "MILESTONE_PLAN_INCOMPLETE"
        api.w.set_plan()
        response = api.call("POST", f"{BASE}/agreement/approve", "freelancer")
        assert response.json()["message"] == "Persetujuan tercatat, menunggu pihak lain"
        body = err(api.call("POST", f"{BASE}/agreement/approve", json={"agreement_version": 9}), 409)
        assert body["code"] == "AGREEMENT_CHANGED"
        response = api.call("POST", f"{BASE}/agreement/approve", json={"agreement_version": 1})
        assert response.json()["message"] == "Kesepakatan final, proyek menunggu pembayaran"
        assert ok(response)["payment"]["status"] == "MENUNGGU"

    def test_request_changes(self, api):
        select(api)
        data = ok(api.call("POST", f"{BASE}/agreement/request-changes", json={"note": "Ubah bobot"}))
        assert data["agreement"]["change_request_note"] == "Ubah bobot"
        err(api.call("POST", f"{BASE}/agreement/request-changes", json={"note": ""}), 422)
        err(api.call("POST", f"{BASE}/agreement/request-changes", "freelancer", json={"note": "x"}), 403)

    def test_cancel(self, api):
        select(api)
        err(api.call("POST", f"{BASE}/cancel", json={"reason": "ASAL"}), 422)
        err(api.call("POST", f"{BASE}/cancel", json={"reason": "LAINNYA"}), 400, "Tuliskan")
        data = ok(api.call("POST", f"{BASE}/cancel", "freelancer", json={"reason": "HARGA_TIDAK_SESUAI"}))
        assert data["cancellation"] == {
            "reason": "HARGA_TIDAK_SESUAI",
            "reason_label": "Harga belum sesuai",
            "note": None,
            "cancelled_by": "FREELANCER",
            "cancelled_at": data["cancellation"]["cancelled_at"],
            "has_payment": False,
        }
        err(api.call("POST", f"{BASE}/cancel", json={"reason": "HARGA_TIDAK_SESUAI"}), 409)

    def test_start_requires_payment(self, api):
        finalize(api)
        err(api.call("POST", f"{BASE}/start", "freelancer"), 409, "belum dibayar")

    def test_my_projects(self, api):
        select(api)
        data = ok(api.call("GET", "/api/v1/workflow/projects"))
        assert data["status_counts"]["MENUNGGU_KESEPAKATAN"] == 1
        assert data["status_counts"]["ALL"] == 1
        assert data["items"][0]["counterpart"]["name"] == "Andi Ramadhan"
        freelancer = ok(api.call("GET", "/api/v1/workflow/projects?status=MENUNGGU_KESEPAKATAN", "freelancer"))
        assert len(freelancer["items"]) == 1
        err(api.call("GET", "/api/v1/workflow/projects?status=ASAL"), 422)
        err(api.call("GET", "/api/v1/workflow/projects", "admin"), 403)


class TestPaymentsApi:
    def test_payment_detail_and_simulation(self, api):
        finalize(api)
        detail = ok(api.call("GET", f"{BASE}/payment"))
        assert detail["status"] == "MENUNGGU"
        assert detail["display_status_label"] == "Menunggu Pembayaran"
        assert 890 <= detail["seconds_remaining"] <= 900
        assert detail["total_amount"] == 1_500_000
        assert detail["agreement"]["duration_days"] == 14

        response = api.call("POST", f"{BASE}/payment/simulate", headers={"Idempotency-Key": "abc-12345"})
        assert response.json()["message"] == "Pembayaran berhasil, dana ditahan TEMUKARYA"
        paid = ok(response)
        assert paid["status"] == "BERHASIL" and paid["fund_status"] == "HELD"
        assert paid["transaction_number"].startswith("TMK-")
        assert paid["expires_at"] is None and paid["seconds_remaining"] is None
        assert paid["attempts"][0]["status"] == "SUCCEEDED"

        again = api.call("POST", f"{BASE}/payment/simulate")
        assert again.json()["message"] == "Pembayaran sudah berhasil sebelumnya"

        wallet = ok(api.call("GET", "/api/v1/wallet", "freelancer"))
        assert wallet == {"available_balance": 0, "held_balance": 1_425_000, "total_balance": 1_425_000}
        entries = ok(api.call("GET", "/api/v1/wallet/transactions?type=HELD", "freelancer"))
        assert entries["items"][0]["type_label"] == "Dana ditahan"

    def test_failed_then_refresh(self, api):
        finalize(api)
        response = api.call("POST", f"{BASE}/payment/simulate", json={"outcome": "FAILED"})
        assert response.json()["message"] == "Pembayaran gagal, silakan coba lagi"
        body = err(api.call("POST", f"{BASE}/payment/simulate"), 409)
        assert body["code"] == "QRIS_REFRESH_REQUIRED"
        assert ok(api.call("POST", f"{BASE}/payment/qris"))["status"] == "MENUNGGU"
        err(api.call("POST", f"{BASE}/payment/simulate", json={"outcome": "MAYBE"}), 422)
        err(api.call("POST", f"{BASE}/payment/simulate", headers={"Idempotency-Key": "pendek"}), 400)

    def test_access(self, api):
        finalize(api)
        err(api.call("POST", f"{BASE}/payment/simulate", "freelancer"), 403)
        err(api.call("GET", f"{BASE}/payment", "other"), 404)
        err(api.call("GET", "/api/v1/wallet"), 403)

    def test_history(self, api):
        finalize(api)
        data = ok(api.call("GET", "/api/v1/payments/history"))
        assert data["counts"] == {"ALL": 1, "PENDING": 1, "HELD": 0, "COMPLETED": 0, "CANCELLED": 0}
        assert data["items"][0]["occurred_at"].endswith("Z")
        err(api.call("GET", "/api/v1/payments/history?group=ASAL"), 422)
        err(api.call("GET", "/api/v1/payments/history", "freelancer"), 403)


class TestSubmissionsApi:
    def test_upload_download_review_flow(self, api):
        to_working(api)
        response = api.call(
            "POST",
            f"{BASE}/submissions",
            "freelancer",
            data={"note": "Draf 1"},
            files=[("files", ("mockup.pdf", PDF, "application/pdf")), ("files", ("logo.png", PNG, "image/png"))],
        )
        submission = ok(response, 201)
        assert submission["version_label"] == "v1.0"
        assert [f["original_file_name"] for f in submission["files"]] == ["mockup.pdf", "logo.png"]
        path = submission["files"][0]["download_path"]

        download = api.call("GET", path, "umkm")
        assert download.status_code == 200
        assert download.content == PDF
        assert download.headers["content-type"] == "application/pdf"
        assert "attachment" in download.headers["content-disposition"]
        err(api.call("GET", path, "other"), 404)

        listing = ok(api.call("GET", f"{BASE}/submissions"))
        assert listing["items"][0]["id"] == submission["id"]
        assert listing["project_status"] == "MENUNGGU_REVIEW"

        revision = ok(
            api.call(
                "POST",
                f"{BASE}/submissions/{submission['id']}/request-revision",
                json={
                    "focus_areas": ["Tipografi & Teks"],
                    "items": [{"title": "Ketebalan font", "detail": "Semi-bold", "area": "Label depan"}],
                },
            )
        )
        assert revision["review"]["decision"] == "REVISION_REQUESTED"
        assert revision["review"]["items"][0]["area"] == "Label depan"

        second = ok(
            api.call(
                "POST",
                f"{BASE}/submissions",
                "freelancer",
                data={"result_url": "https://drive.google.com/v2"},
            ),
            201,
        )
        assert second["version_label"] == "v1.1"

        done = ok(
            api.call(
                "POST",
                f"{BASE}/submissions/{second['id']}/approve",
                json={"review": {"rating": 5, "review_text": "Mantap", "highlights": ["TEPAT_WAKTU"]}},
            )
        )
        assert done["project_status"] == "SELESAI"
        assert done["payment"]["fund_status"] == "RELEASED"
        assert done["payment"]["freelancer_amount"] == 1_425_000
        assert done["review"]["highlights"] == [{"value": "TEPAT_WAKTU", "label": "Tepat Waktu"}]
        again = api.call("POST", f"{BASE}/submissions/{second['id']}/approve")
        assert again.json()["message"] == "Proyek sudah selesai sebelumnya"
        wallet = ok(api.call("GET", "/api/v1/wallet", "freelancer"))
        assert wallet["available_balance"] == 1_425_000

    def test_upload_errors(self, api):
        to_working(api)
        err(api.call("POST", f"{BASE}/submissions", "freelancer"), 400, "Lampirkan")
        err(
            api.call("POST", f"{BASE}/submissions", "freelancer", files=[("files", ("a.exe", b"MZ", "x/y"))]),
            415,
        )
        err(
            api.call("POST", f"{BASE}/submissions", "freelancer", files=[("files", ("a.pdf", PNG, "application/pdf"))]),
            400,
            "tidak sesuai",
        )
        err(api.call("POST", f"{BASE}/submissions", "umkm", data={"result_url": "https://x.id/a"}), 403)

    def test_review_validation(self, api):
        submission = to_review(api)
        err(api.call("POST", f"{BASE}/submissions/{submission['id']}/request-revision", json={}), 400, "wajib")
        err(
            api.call("POST", f"{BASE}/submissions/{submission['id']}/request-revision", json={"items": [{"title": ""}]}),
            422,
        )
        err(api.call("POST", f"{BASE}/submissions/{submission['id']}/approve", json={"review": {"rating": 6}}), 422)
        err(api.call("POST", f"{BASE}/submissions/nope/approve"), 404)


class TestReviewsApi:
    def test_review_endpoints(self, api):
        submission = to_review(api)
        err(api.call("POST", f"{BASE}/review", json={"rating": 5}), 409)
        ok(api.call("POST", f"{BASE}/submissions/{submission['id']}/approve"))
        err(api.call("GET", f"{BASE}/review"), 404)
        created = ok(api.call("POST", f"{BASE}/review", json={"rating": 4, "highlights": ["PAHAM_KEBUTUHAN"]}), 201)
        assert created["rating"] == 4
        err(api.call("POST", f"{BASE}/review", json={"rating": 4}), 409)
        assert ok(api.call("GET", f"{BASE}/review", "freelancer"))["id"] == created["id"]
        public = ok(api.call("GET", f"/api/v1/freelancers/{FREELANCER_ID}/reviews", "other"))
        assert public["review_count"] == 1 and public["average_rating"] == 4.0
        assert public["items"][0]["reviewer"]["business_name"] == "Kedai Kopi Senja"
        err(api.call("GET", f"/api/v1/freelancers/{UMKM_ID}/reviews"), 404)
        err(api.call("POST", f"{BASE}/review", json={"rating": 0}), 422)
        err(api.call("POST", f"{BASE}/review", json={"rating": 5, "highlights": ["ASAL"]}), 422)


class TestNotificationsApi:
    def test_list_and_mark(self, api):
        select(api)
        data = ok(api.call("GET", "/api/v1/notifications", "freelancer"))
        assert data["unread_count"] == 1
        assert data["counts"] == {"ALL": 1, "PROJECT": 1, "PAYMENT": 0, "MESSAGE": 0}
        item = data["items"][0]
        assert (item["type"], item["category"], item["reference_type"], item["is_read"]) == (
            "APPLICATION_ACCEPTED",
            "PROJECT",
            "PROJECT",
            False,
        )
        assert ok(api.call("GET", "/api/v1/notifications/unread-count", "freelancer")) == {"unread_count": 1}
        read = ok(api.call("PATCH", f"/api/v1/notifications/{item['id']}/read", "freelancer"))
        assert read["is_read"] is True
        err(api.call("PATCH", f"/api/v1/notifications/{item['id']}/read", "umkm"), 404)
        assert ok(api.call("PATCH", "/api/v1/notifications/read-all", "freelancer")) == {"updated": 0}
        assert ok(api.call("GET", "/api/v1/notifications?category=PAYMENT", "freelancer"))["items"] == []
        err(api.call("GET", "/api/v1/notifications?category=ASAL", "freelancer"), 422)


class TestMilestonePlanApi:
    def test_save_plan_and_complete(self, api):
        response = api.call(
            "PUT",
            "/api/v1/projects/p1/milestones",
            "freelancer",
            json={"items": [{"name": "Riset", "weight_percent": "20"}, {"name": "Konsep", "weight_percent": 80}]},
        )
        plan = ok(response)
        assert plan["is_plan_complete"] is True
        assert [i["sort_order"] for i in plan["items"]] == [1, 2]
        assert api.milestone_repo.resets == 1
        err(
            api.call("PUT", "/api/v1/projects/p1/milestones", "freelancer", json={"items": [{"name": "x", "weight_percent": "10.555"}]}),
            422,
        )
        err(
            api.call("PUT", "/api/v1/projects/p1/milestones", "freelancer", json={"items": [{"name": "x", "weight_percent": 0}]}),
            422,
        )
        err(api.call("PATCH", f"/api/v1/projects/p1/milestones/{plan['items'][0]['id']}/complete", "freelancer"), 409)
        api.milestone_repo.context = api.milestone_repo.context.__class__(
            **{**{f: getattr(api.milestone_repo.context, f) for f in api.milestone_repo.context.__slots__}, "status": "SEDANG_DIKERJAKAN"}
        )
        progress = ok(api.call("PATCH", f"/api/v1/projects/p1/milestones/{plan['items'][0]['id']}/complete", "freelancer"))
        assert Decimal(str(progress["progress_percent"])) == Decimal("20")


class TestAdminFinanceApi:
    def test_endpoints(self, api):
        to_working(api)
        summary = ok(api.call("GET", "/api/v1/admin/finance/summary", "admin"))
        assert summary["total_income"] == 75_000 and summary["held_amount"] == 1_425_000
        transactions = ok(api.call("GET", "/api/v1/admin/finance/transactions?status=BERHASIL", "admin"))
        assert transactions["total"] == 1
        payment_id = transactions["items"][0]["payment_id"]
        detail = ok(api.call("GET", f"/api/v1/admin/finance/transactions/{payment_id}", "admin"))
        assert detail["attempts"][0]["status"] == "SUCCEEDED"
        err(api.call("GET", "/api/v1/admin/finance/transactions/nope", "admin"), 404)
        commissions = ok(api.call("GET", "/api/v1/admin/finance/commissions", "admin"))
        assert commissions["total_commission"] == 75_000
        chart = ok(api.call("GET", "/api/v1/admin/finance/income-chart?period=MONTH", "admin"))
        assert chart["points"][-1]["income"] == 75_000
        err(api.call("GET", "/api/v1/admin/finance/transactions?status=ASAL", "admin"), 422)
        err(api.call("GET", "/api/v1/admin/finance/income-chart?date_from=2026-12-01&date_to=2026-11-01", "admin"), 400)
