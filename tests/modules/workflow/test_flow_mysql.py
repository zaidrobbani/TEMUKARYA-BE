"""Alur lengkap TEMUKARYA terhadap MySQL sungguhan + uji permintaan bersamaan.

Jalankan dengan TEMUKARYA_RUN_MYSQL_TESTS=1 pada DB `temukarya` lokal/sementara.
Data yang dibuat dihapus lagi di akhir test.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import bindparam, text

from app.core.database import SessionLocal, engine
from app.core.dependencies import SqlAlchemyUnitOfWork
from app.core.exceptions import ConflictError
from app.main import app
from app.modules.auth.presentation.dependencies import get_current_user
from app.modules.notifications.application.use_cases import Notifier
from app.modules.notifications.infrastructure.repositories import SqlAlchemyNotificationRepository
from app.modules.payments.application.use_cases import FundReleaser, SimulatePayment
from app.modules.payments.domain.entities import PaymentOutcome
from app.modules.payments.infrastructure.repositories import SqlAlchemyPaymentRepository, SqlAlchemyWalletRepository
from app.modules.reviews.application.use_cases import ReviewCreator
from app.modules.reviews.infrastructure.repositories import SqlAlchemyReviewRepository
from app.modules.submissions.application.use_cases import ApproveSubmission
from app.modules.submissions.infrastructure.repositories import SqlAlchemySubmissionRepository
from app.modules.submissions.infrastructure.storage import LocalSubmissionFileStorage
from app.modules.submissions.presentation.dependencies import get_submission_storage
from app.modules.users.domain.entities import User, UserRole
from app.modules.workflow.application.dto import Actor, SelectFreelancerInput
from app.modules.workflow.application.use_cases import SelectFreelancer
from app.modules.workflow.infrastructure.repositories import SqlAlchemyWorkflowRepository
from tests.modules.workflow.world import PDF

pytestmark = pytest.mark.skipif(
    os.getenv("TEMUKARYA_RUN_MYSQL_TESTS") != "1"
    or engine.url.get_backend_name() != "mysql"
    or engine.url.host not in ("localhost", "127.0.0.1", "db")
    or engine.url.database != "temukarya",
    reason="MySQL integration tests disabled",
)

TABLES_BY_PROJECT = [
    ("notifications", "reference_id IN :pids"),
    ("wallet_transactions", "payment_id IN (SELECT p.id FROM payments p JOIN project_agreements a "
     "ON a.id = p.agreement_id WHERE a.project_id IN :pids)"),
    ("payment_attempts", "payment_id IN (SELECT p.id FROM payments p JOIN project_agreements a "
     "ON a.id = p.agreement_id WHERE a.project_id IN :pids)"),
    ("payments", "agreement_id IN (SELECT id FROM project_agreements WHERE project_id IN :pids)"),
    ("submission_reviews", "submission_id IN (SELECT id FROM project_submissions WHERE project_id IN :pids)"),
    ("submission_files", "submission_id IN (SELECT id FROM project_submissions WHERE project_id IN :pids)"),
    ("project_submissions", "project_id IN :pids"),
    ("freelancer_reviews", "project_id IN :pids"),
    ("project_milestones", "project_id IN :pids"),
    ("project_status_history", "project_id IN :pids"),
    ("project_agreements", "project_id IN :pids"),
    ("project_applications", "project_id IN :pids"),
    ("projects", "id IN :pids"),
]


class Seed:
    def __init__(self):
        tag = uuid4().hex[:8]
        self.umkm, self.f1, self.f2, self.admin = (str(uuid4()) for _ in range(4))
        self.users = [self.umkm, self.f1, self.f2, self.admin]
        self.projects: list[str] = []
        now = datetime.now(UTC).replace(tzinfo=None)
        with engine.begin() as conn:
            for uid, role, name in (
                (self.umkm, "UMKM", "Rina Pratiwi"),
                (self.f1, "FREELANCER", "Andi Ramadhan"),
                (self.f2, "FREELANCER", "Maya Safitri"),
                (self.admin, "ADMIN", "Admin"),
            ):
                conn.execute(
                    text(
                        "INSERT INTO users (id, name, email, password_hash, role, email_verified_at) "
                        "VALUES (:id, :name, :email, '-', :role, :now)"
                    ),
                    {"id": uid, "name": name, "email": f"{uid[:8]}-{tag}@test.id", "role": role, "now": now},
                )
            conn.execute(
                text(
                    "INSERT INTO umkm_profiles (user_id, business_name, business_category, business_address, city) "
                    "VALUES (:id, 'Kedai Kopi Senja', 'Kuliner', 'Jl. Braga', 'Bandung')"
                ),
                {"id": self.umkm},
            )
            for uid, title in ((self.f1, "Desainer Grafis"), (self.f2, "Fotografer")):
                conn.execute(
                    text(
                        "INSERT INTO freelancer_profiles (user_id, professional_title, city) "
                        "VALUES (:id, :title, 'Yogyakarta')"
                    ),
                    {"id": uid, "title": title},
                )

    def project(self, title="Rebranding Pouch Kopi", budget=1_500_000) -> str:
        project_id = str(uuid4())
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO projects (id, umkm_id, category_id, title, description, budget, deadline, status, "
                    "published_at) VALUES (:id, :umkm, 'graphic_design', :title, 'Desain logo + kemasan', :budget, "
                    ":deadline, 'TERBUKA', :now)"
                ),
                {
                    "id": project_id,
                    "umkm": self.umkm,
                    "title": title,
                    "budget": budget,
                    "deadline": date.today() + timedelta(days=30),
                    "now": datetime.now(UTC).replace(tzinfo=None),
                },
            )
        self.projects.append(project_id)
        return project_id

    def cleanup(self):
        with engine.begin() as conn:
            if self.projects:
                for table, condition in TABLES_BY_PROJECT:
                    statement = text(f"DELETE FROM {table} WHERE {condition}")
                    conn.execute(statement.bindparams(bindparam("pids", expanding=True)), {"pids": self.projects})
            for sql in (
                "DELETE FROM messages WHERE conversation_id IN "
                "(SELECT id FROM conversations WHERE umkm_id IN :u OR freelancer_id IN :u)",
                "DELETE FROM conversations WHERE umkm_id IN :u OR freelancer_id IN :u",
                "DELETE FROM notifications WHERE user_id IN :u",
                "DELETE FROM wallets WHERE freelancer_id IN :u",
                "DELETE FROM freelancer_profiles WHERE user_id IN :u",
                "DELETE FROM umkm_profiles WHERE user_id IN :u",
                "DELETE FROM users WHERE id IN :u",
            ):
                conn.execute(text(sql).bindparams(bindparam("u", expanding=True)), {"u": self.users})

    def scalar(self, sql: str, **params):
        with engine.connect() as conn:
            return conn.execute(text(sql), params).scalar_one()


@pytest.fixture
def seed():
    data = Seed()
    yield data
    data.cleanup()


@pytest.fixture
def client(seed, tmp_path):
    holder = {"user": None}
    roles = {seed.umkm: UserRole.UMKM, seed.f1: UserRole.FREELANCER, seed.f2: UserRole.FREELANCER,
             seed.admin: UserRole.ADMIN}

    def current_user():
        uid = holder["user"]
        return User(name=uid, email="x@test.id", password_hash="-", role=roles[uid], id=uid)

    app.dependency_overrides = {
        get_current_user: current_user,
        get_submission_storage: lambda: LocalSubmissionFileStorage(tmp_path),
    }
    with TestClient(app, raise_server_exceptions=os.getenv("RAISE") == "1") as test_client:
        def call(method, path, user, **kwargs):
            holder["user"] = user
            return test_client.request(method, "/api/v1" + path, **kwargs)

        yield call
    app.dependency_overrides = {}


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def test_full_flow_with_revision_payment_and_release(seed, client):
    pid = seed.project()
    p = f"/projects/{pid}"

    ok(client("POST", f"{p}/applications", seed.f1,
              json={"proposed_price": 1_500_000, "estimated_duration_days": 14, "proposal_message": "Siap"}), 201)
    ok(client("POST", f"{p}/applications", seed.f2,
              json={"proposed_price": 1_200_000, "estimated_duration_days": 10, "proposal_message": "Bisa"}), 201)
    received = ok(client("GET", "/notifications?category=PROJECT", seed.umkm))
    assert [n["type"] for n in received["items"]] == ["APPLICATION_RECEIVED", "APPLICATION_RECEIVED"]

    apps = ok(client("GET", f"{p}/applications", seed.umkm))
    app_id = next(a["id"] for a in apps["items"] if a["freelancer_id"] == seed.f1)
    detail = ok(client("POST", f"{p}/agreement", seed.umkm, json={"application_id": app_id}), 201)
    assert detail["project"]["status"] == "MENUNGGU_KESEPAKATAN"
    assert detail["agreement"]["duration_days"] == 14
    with engine.connect() as conn:
        statuses = dict(
            conn.execute(text("SELECT freelancer_id, status FROM project_applications WHERE project_id = :p"), {"p": pid}).all()
        )
    assert statuses == {seed.f1: "ACCEPTED", seed.f2: "NOT_SELECTED"}
    assert ok(client("GET", "/workflow/projects", seed.f1))["items"][0]["project"]["id"] == pid

    # Rencana pengerjaan disusun freelancer; milestone terbaca oleh freelancer terpilih.
    plan = ok(client("PUT", f"{p}/milestones", seed.f1, json={"items": [
        {"name": "Riset & Moodboard", "weight_percent": 20},
        {"name": "Konsep Logo", "weight_percent": 30},
        {"name": "Desain Pouch", "weight_percent": 35},
        {"name": "Mockup", "weight_percent": "15.00"},
    ]}))
    assert plan["is_plan_complete"] is True
    assert len(ok(client("GET", f"{p}/milestones", seed.f1))["items"]) == 4
    assert client("GET", f"{p}/milestones", seed.f2).status_code == 404

    ok(client("POST", f"{p}/agreement/approve", seed.f1))
    changed = ok(client("PATCH", f"{p}/agreement", seed.umkm, json={"agreed_price": 1_600_000}))
    assert changed["agreement"]["agreement_version"] == 3  # rencana + harga = 2 perubahan
    assert changed["agreement"]["freelancer_approved_at"] is None
    assert client("POST", f"{p}/agreement/approve", seed.umkm, json={"agreement_version": 2}).status_code == 409
    ok(client("POST", f"{p}/agreement/approve", seed.umkm, json={"agreement_version": 3}))
    final = ok(client("POST", f"{p}/agreement/approve", seed.f1))
    assert final["project"]["status"] == "MENUNGGU_PEMBAYARAN"
    assert client("PUT", f"{p}/milestones", seed.f1, json={"items": []}).status_code == 409

    payment = ok(client("GET", f"{p}/payment", seed.umkm))
    assert (payment["gross_amount"], payment["platform_fee_amount"], payment["freelancer_amount"]) == (
        1_600_000, 80_000, 1_520_000)
    ok(client("POST", f"{p}/payment/simulate", seed.umkm, json={"outcome": "FAILED"}))
    assert client("POST", f"{p}/payment/simulate", seed.umkm).json()["code"] == "QRIS_REFRESH_REQUIRED"
    ok(client("POST", f"{p}/payment/qris", seed.umkm))
    paid = ok(client("POST", f"{p}/payment/simulate", seed.umkm, headers={"Idempotency-Key": f"k-{pid}"}))
    assert paid["status"] == "BERHASIL" and paid["transaction_number"].startswith("TMK-")
    replay = ok(client("POST", f"{p}/payment/simulate", seed.umkm, headers={"Idempotency-Key": f"k-{pid}"}))
    assert replay["id"] == paid["id"] and len(replay["attempts"]) == 2
    assert ok(client("GET", "/wallet", seed.f1))["held_balance"] == 1_520_000

    assert client("PATCH", f"{p}/milestones/{plan['items'][0]['id']}/complete", seed.f1).status_code == 409
    ok(client("POST", f"{p}/start", seed.f1))
    for _ in range(2):
        progress = ok(client("PATCH", f"{p}/milestones/{plan['items'][0]['id']}/complete", seed.f1))
    assert float(progress["progress_percent"]) == 20.0
    risk = ok(client("GET", f"{p}/milestones/delay-risk", seed.umkm))
    assert risk["total_days"] >= 1

    first = ok(client("POST", f"{p}/submissions", seed.f1, data={"note": "Draf 1"},
                      files=[("files", ("mockup.pdf", PDF, "application/pdf"))]), 201)
    download = client("GET", first["files"][0]["download_path"].removeprefix("/api/v1"), seed.umkm)
    assert download.status_code == 200 and download.content == PDF
    ok(client("POST", f"{p}/submissions/{first['id']}/request-revision", seed.umkm,
              json={"focus_areas": ["Tipografi"], "items": [{"title": "Font", "detail": "Semi-bold"}]}))
    second = ok(client("POST", f"{p}/submissions", seed.f1, data={"result_url": "https://drive.google.com/v2"}), 201)
    assert second["version_label"] == "v1.1"
    listing = ok(client("GET", f"{p}/submissions", seed.umkm))
    assert listing["revision_count"] == 1
    assert listing["items"][1]["review"]["items"] == [{"title": "Font", "detail": "Semi-bold", "area": None}]

    done = ok(client("POST", f"{p}/submissions/{second['id']}/approve", seed.umkm,
                     json={"review": {"rating": 5, "review_text": "Mantap", "highlights": ["TEPAT_WAKTU"]}}))
    assert done["project_status"] == "SELESAI" and done["payment"]["fund_status"] == "RELEASED"
    ok(client("POST", f"{p}/submissions/{second['id']}/approve", seed.umkm))
    assert ok(client("GET", "/wallet", seed.f1)) == {
        "available_balance": 1_520_000, "held_balance": 0, "total_balance": 1_520_000}
    assert seed.scalar(
        "SELECT COUNT(*) FROM wallet_transactions t JOIN payments p ON p.id = t.payment_id "
        "JOIN project_agreements a ON a.id = p.agreement_id WHERE a.project_id = :p", p=pid) == 3
    entries = ok(client("GET", "/wallet/transactions", seed.f1))["items"]
    assert [e["type"] for e in entries] == ["FUND_RELEASED", "FUND_HELD"]

    history = ok(client("GET", "/payments/history?group=COMPLETED", seed.umkm))
    assert history["items"][0]["display_status"] == "SELESAI"
    reviews = ok(client("GET", f"/freelancers/{seed.f1}/reviews", seed.umkm))
    assert reviews["review_count"] == 1 and reviews["items"][0]["reviewer"]["business_name"] == "Kedai Kopi Senja"
    workflow = ok(client("GET", f"{p}/workflow", seed.f1))
    assert [h["new_status"] for h in workflow["history"]] == [
        "MENUNGGU_KESEPAKATAN", "MENUNGGU_PEMBAYARAN", "SIAP_DIKERJAKAN", "SEDANG_DIKERJAKAN",
        "MENUNGGU_REVIEW", "REVISI", "MENUNGGU_REVIEW", "SELESAI"]
    assert workflow["has_review"] is True

    freelancer_types = [n["type"] for n in ok(client("GET", "/notifications?limit=100", seed.f1))["items"]]
    for expected in ("APPLICATION_ACCEPTED", "AGREEMENT_FINALIZED", "PAYMENT_RECEIVED", "REVISION_REQUESTED",
                     "SUBMISSION_APPROVED", "FUNDS_RELEASED", "REVIEW_RECEIVED"):
        assert expected in freelancer_types
    assert ok(client("PATCH", "/notifications/read-all", seed.umkm))["updated"] > 0
    assert ok(client("GET", "/notifications/unread-count", seed.umkm))["unread_count"] == 0

    summary = ok(client("GET", "/admin/finance/summary", seed.admin))
    assert summary["total_income"] >= 80_000
    tx = ok(client("GET", f"/admin/finance/transactions?search={paid['transaction_number']}", seed.admin))
    assert tx["total"] == 1 and tx["items"][0]["umkm_business_name"] == "Kedai Kopi Senja"
    tx_detail = ok(client("GET", f"/admin/finance/transactions/{paid['id']}", seed.admin))
    assert [a["status"] for a in tx_detail["attempts"]] == ["FAILED", "SUCCEEDED"]
    chart = ok(client("GET", "/admin/finance/income-chart", seed.admin))
    assert sum(point["income"] for point in chart["points"]) >= 80_000


def test_cancel_and_chat_notification(seed, client):
    pid = seed.project("Foto Menu")
    p = f"/projects/{pid}"
    ok(client("POST", f"{p}/agreement", seed.umkm, json={"freelancer_id": seed.f2}), 201)
    cancelled = ok(client("POST", f"{p}/cancel", seed.f2, json={"reason": "JADWAL_TIDAK_COCOK"}))
    assert cancelled["cancellation"]["cancelled_by"] == "FREELANCER"
    assert cancelled["agreement"]["status"] == "CANCELLED"
    assert ok(client("GET", "/notifications", seed.umkm))["items"][0]["type"] == "PROJECT_CANCELLED"
    assert client("POST", f"{p}/start", seed.f2).status_code == 409

    conversation = ok(client("POST", "/conversations", seed.umkm, json={"counterpart_user_id": seed.f1}))
    ok(client("POST", f"/conversations/{conversation['id']}/messages", seed.umkm,
              json={"message_text": "Halo Mas Andi"}), 201)
    message = ok(client("GET", "/notifications?category=MESSAGE", seed.f1))["items"][0]
    assert message["title"] == "Pesan baru dari Rina Pratiwi"
    assert message["reference_id"] == conversation["id"]


def _session_use_cases(session):
    workflow = SqlAlchemyWorkflowRepository(session)
    payments = SqlAlchemyPaymentRepository(session)
    wallets = SqlAlchemyWalletRepository(session)
    notifier = Notifier(SqlAlchemyNotificationRepository(session))
    uow = SqlAlchemyUnitOfWork(session)
    return workflow, payments, wallets, notifier, uow


def _run_together(fn, *args_list):
    barrier = threading.Barrier(len(args_list))

    def worker(args):
        session = SessionLocal()
        try:
            barrier.wait()
            return "ok", fn(session, *args)
        except ConflictError as exc:
            return "conflict", exc.message
        finally:
            session.close()

    with ThreadPoolExecutor(len(args_list)) as pool:
        return list(pool.map(worker, args_list))


def test_concurrent_select_pay_and_release(seed, client):
    pid = seed.project()
    p = f"/projects/{pid}"
    for uid in (seed.f1, seed.f2):
        ok(client("POST", f"{p}/applications", uid,
                  json={"proposed_price": 1_000_000, "estimated_duration_days": 7, "proposal_message": "Siap"}), 201)
    apps = {a["freelancer_id"]: a["id"] for a in ok(client("GET", f"{p}/applications", seed.umkm))["items"]}

    def select(session, app_id):
        workflow, _, _, notifier, uow = _session_use_cases(session)
        return SelectFreelancer(workflow, notifier, uow).execute(
            Actor(seed.umkm, "UMKM"), pid, SelectFreelancerInput(application_id=app_id)
        )

    results = _run_together(select, (apps[seed.f1],), (apps[seed.f2],))
    assert sorted(r[0] for r in results) == ["conflict", "ok"]
    assert seed.scalar("SELECT COUNT(*) FROM project_agreements WHERE project_id = :p", p=pid) == 1
    chosen = seed.scalar("SELECT freelancer_id FROM project_agreements WHERE project_id = :p", p=pid)

    ok(client("PUT", f"{p}/milestones", chosen, json={"items": [{"name": "Semua", "weight_percent": 100}]}))
    ok(client("POST", f"{p}/agreement/approve", chosen))
    ok(client("POST", f"{p}/agreement/approve", seed.umkm))

    def pay(session, key):
        workflow, payments, wallets, notifier, uow = _session_use_cases(session)
        return SimulatePayment(workflow, payments, wallets, notifier, uow).execute(
            Actor(seed.umkm, "UMKM"), pid, PaymentOutcome.SUCCESS, key
        )

    results = _run_together(pay, (f"a-{pid}",), (f"b-{pid}",))
    assert [r[0] for r in results] == ["ok", "ok"]
    assert sorted(r[1].already_paid for r in results) == [False, True]
    assert seed.scalar(
        "SELECT COUNT(*) FROM payment_attempts t JOIN payments p ON p.id = t.payment_id "
        "JOIN project_agreements a ON a.id = p.agreement_id WHERE a.project_id = :p", p=pid) == 1
    assert ok(client("GET", "/wallet", chosen))["held_balance"] == 950_000

    ok(client("POST", f"{p}/start", chosen))
    submission = ok(client("POST", f"{p}/submissions", chosen, data={"result_url": "https://x.id/hasil"}), 201)

    def approve(session, _):
        workflow, payments, wallets, notifier, uow = _session_use_cases(session)
        return ApproveSubmission(
            workflow,
            SqlAlchemySubmissionRepository(session),
            FundReleaser(payments, wallets),
            ReviewCreator(SqlAlchemyReviewRepository(session), notifier),
            notifier,
            uow,
        ).execute(Actor(seed.umkm, "UMKM"), pid, submission["id"])

    results = _run_together(approve, (1,), (2,))
    assert [r[0] for r in results] == ["ok", "ok"]
    assert sorted(r[1].already_completed for r in results) == [False, True]
    assert ok(client("GET", "/wallet", chosen)) == {
        "available_balance": 950_000, "held_balance": 0, "total_balance": 950_000}
    assert seed.scalar(
        "SELECT COUNT(*) FROM wallet_transactions t JOIN payments p ON p.id = t.payment_id "
        "JOIN project_agreements a ON a.id = p.agreement_id WHERE a.project_id = :p "
        "AND t.transaction_type = 'FUND_RELEASED'", p=pid) == 2
