"""Merakit semua use case workflow/payments/submissions/reviews dengan fake repository bersama."""

import io
from decimal import Decimal

from app.modules.notifications.application.use_cases import Notifier
from app.modules.payments.application.use_cases import (
    FundReleaser,
    GetProjectPayment,
    GetWallet,
    ListPaymentHistory,
    ListWalletEntries,
    PaymentService,
    RefreshQris,
    SimulatePayment,
)
from app.modules.payments.domain.entities import PaymentOutcome
from app.modules.reviews.application.use_cases import (
    CreateReview,
    GetProjectReview,
    ListFreelancerReviews,
    ReviewCreator,
    ReviewInput,
)
from app.modules.submissions.application.use_cases import (
    ApproveSubmission,
    GetSubmission,
    ListSubmissions,
    OpenSubmissionFile,
    RequestRevision,
    RevisionRequestInput,
    SubmitResult,
    SubmitResultInput,
    UploadedFile,
)
from app.modules.workflow.application.dto import (
    Actor,
    CancelProjectInput,
    SelectFreelancerInput,
    UpdateAgreementInput,
)
from app.modules.workflow.application.use_cases import (
    ApproveAgreement,
    CancelProject,
    GetAgreement,
    GetProjectWorkflow,
    ListMyProjects,
    RequestAgreementChanges,
    SelectFreelancer,
    StartWork,
    UpdateAgreement,
)
from tests.fakes import FakeUnitOfWork
from tests.modules.workflow.fakes import (
    FREELANCER_ID,
    OTHER_FREELANCER_ID,
    OTHER_UMKM_ID,
    PROJECT_ID,
    UMKM_ID,
    Clock,
    FakeMilestoneWeights,
    FakeNotificationRepository,
    FakePaymentRepository,
    FakeReviewRepository,
    FakeStorage,
    FakeSubmissionRepository,
    FakeWalletRepository,
    FakeWorkflowRepository,
    Store,
)

UMKM = Actor(UMKM_ID, "UMKM")
FREELANCER = Actor(FREELANCER_ID, "FREELANCER")
OTHER_FREELANCER = Actor(OTHER_FREELANCER_ID, "FREELANCER")
OTHER_UMKM = Actor(OTHER_UMKM_ID, "UMKM")
ADMIN = Actor("admin-1", "ADMIN")

PDF = b"%PDF-1.7\n" + b"x" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 100


def upload(name: str = "mockup.pdf", content: bytes = PDF, size: int | None = None) -> UploadedFile:
    return UploadedFile(name, len(content) if size is None else size, io.BytesIO(content))


class World:
    def __init__(self):
        self.store = Store()
        self.clock = Clock()
        self.uow = FakeUnitOfWork()
        self.workflow = FakeWorkflowRepository(self.store)
        self.payments = FakePaymentRepository(self.store)
        self.wallets = FakeWalletRepository(self.store)
        self.submissions = FakeSubmissionRepository(self.store)
        self.reviews = FakeReviewRepository(self.store)
        self.storage = FakeStorage()
        self.notifier = Notifier(FakeNotificationRepository(self.store), self.clock)
        self.milestones = FakeMilestoneWeights(self.store)
        self.numbers: list[str] = []

        self.store.add_user(UMKM_ID, "UMKM", "Rina Pratiwi", "Kedai Kopi Senja")
        self.store.add_user(OTHER_UMKM_ID, "UMKM", "Budi", "Warung Budi")
        self.store.add_user(FREELANCER_ID, "FREELANCER", "Andi Ramadhan", "Desainer Grafis")
        self.store.add_user(OTHER_FREELANCER_ID, "FREELANCER", "Maya Safitri", "Fotografer")
        self.store.add_project()

    # ---- use case ----
    def select(self, actor=UMKM, project_id=PROJECT_ID, **data):
        return SelectFreelancer(self.workflow, self.notifier, self.uow, self.clock).execute(
            actor, project_id, SelectFreelancerInput(**data)
        )

    def detail(self, actor=UMKM, project_id=PROJECT_ID):
        return GetProjectWorkflow(self.workflow).execute(actor, project_id)

    def get_agreement(self, actor=UMKM, project_id=PROJECT_ID):
        return GetAgreement(self.workflow).execute(actor, project_id)

    def update_agreement(self, actor=UMKM, project_id=PROJECT_ID, **data):
        return UpdateAgreement(self.workflow, self.notifier, self.uow, self.clock).execute(
            actor, project_id, UpdateAgreementInput(**data)
        )

    def approve(self, actor=UMKM, project_id=PROJECT_ID, version=None):
        return ApproveAgreement(
            self.workflow, self.milestones, PaymentService(self.payments), self.notifier, self.uow, self.clock
        ).execute(actor, project_id, version)

    def request_changes(self, actor=UMKM, note="Tolong pecah milestone konsep logo", project_id=PROJECT_ID):
        return RequestAgreementChanges(self.workflow, self.notifier, self.uow, self.clock).execute(
            actor, project_id, note
        )

    def cancel(self, actor=UMKM, reason="HARGA_TIDAK_SESUAI", note=None, project_id=PROJECT_ID):
        return CancelProject(
            self.workflow, PaymentService(self.payments), self.notifier, self.uow, self.clock
        ).execute(actor, project_id, CancelProjectInput(reason, note))

    def start(self, actor=FREELANCER, project_id=PROJECT_ID):
        return StartWork(self.workflow, self.notifier, self.uow, self.clock).execute(actor, project_id)

    def my_projects(self, actor=UMKM, status=None, limit=20, offset=0):
        return ListMyProjects(self.workflow).execute(actor, status, limit, offset)

    def get_payment(self, actor=UMKM, project_id=PROJECT_ID):
        return GetProjectPayment(self.workflow, self.payments, self.clock).execute(actor, project_id)

    def refresh_qris(self, actor=UMKM, project_id=PROJECT_ID):
        return RefreshQris(self.workflow, self.payments, self.uow, self.clock).execute(actor, project_id)

    def _number(self, now):
        number = f"TMK-20261110-{len(self.numbers):05d}"
        self.numbers.append(number)
        return number

    def pay(self, actor=UMKM, outcome=PaymentOutcome.SUCCESS, key=None, project_id=PROJECT_ID, numbers=None):
        return SimulatePayment(
            self.workflow,
            self.payments,
            self.wallets,
            self.notifier,
            self.uow,
            self.clock,
            numbers or self._number,
        ).execute(actor, project_id, outcome, key)

    def history(self, actor=UMKM, **kwargs):
        return ListPaymentHistory(self.payments).execute(actor, **kwargs)

    def wallet(self, actor=FREELANCER):
        return GetWallet(self.wallets).execute(actor)

    def wallet_entries(self, actor=FREELANCER, **kwargs):
        return ListWalletEntries(self.wallets).execute(actor, **kwargs)

    def submit(self, actor=FREELANCER, note="Mohon dicek", url=None, files=(), project_id=PROJECT_ID):
        return SubmitResult(
            self.workflow, self.submissions, self.storage, self.notifier, self.uow, self.clock
        ).execute(actor, project_id, SubmitResultInput(note, url, tuple(files)))

    def list_submissions(self, actor=UMKM, project_id=PROJECT_ID):
        return ListSubmissions(self.workflow, self.submissions, self.clock).execute(actor, project_id)

    def get_submission(self, submission_id, actor=UMKM, project_id=PROJECT_ID):
        return GetSubmission(self.workflow, self.submissions, self.clock).execute(actor, project_id, submission_id)

    def open_file(self, submission_id, file_id, actor=UMKM, project_id=PROJECT_ID):
        return OpenSubmissionFile(self.workflow, self.submissions, self.storage, self.clock).execute(
            actor, project_id, submission_id, file_id
        )

    def request_revision(self, submission_id, actor=UMKM, project_id=PROJECT_ID, **data):
        data.setdefault("note", "Tebalkan font varian")
        return RequestRevision(self.workflow, self.submissions, self.notifier, self.uow, self.clock).execute(
            actor, project_id, submission_id, RevisionRequestInput(**data)
        )

    def review_creator(self):
        return ReviewCreator(self.reviews, self.notifier)

    def approve_submission(self, submission_id, actor=UMKM, project_id=PROJECT_ID, review: ReviewInput | None = None):
        return ApproveSubmission(
            self.workflow,
            self.submissions,
            FundReleaser(self.payments, self.wallets),
            self.review_creator(),
            self.notifier,
            self.uow,
            self.clock,
        ).execute(actor, project_id, submission_id, review)

    def create_review(self, actor=UMKM, project_id=PROJECT_ID, **data):
        data.setdefault("rating", 5)
        return CreateReview(self.workflow, self.review_creator(), self.uow, self.clock).execute(
            actor, project_id, ReviewInput(**data)
        )

    def get_review(self, actor=UMKM, project_id=PROJECT_ID):
        return GetProjectReview(self.workflow, self.reviews).execute(actor, project_id)

    def freelancer_reviews(self, freelancer_id=FREELANCER_ID, limit=20, offset=0):
        return ListFreelancerReviews(self.workflow, self.reviews).execute(freelancer_id, limit, offset)

    # ---- alur ----
    def set_plan(self, weights=("40", "60"), project_id=PROJECT_ID):
        self.store.milestones[project_id] = [(Decimal(w), False) for w in weights]

    def to_negotiation(self):
        self.store.add_application()
        self.select(application_id=f"app-{FREELANCER_ID}-{PROJECT_ID}")

    def to_waiting_payment(self):
        self.to_negotiation()
        self.set_plan()
        self.approve(FREELANCER)
        self.approve(UMKM)

    def to_ready(self):
        self.to_waiting_payment()
        self.pay()

    def to_working(self):
        self.to_ready()
        self.start()

    def to_review(self):
        self.to_working()
        return self.submit(url="https://drive.google.com/hasil-v1")

    def to_completed(self):
        submission = self.to_review()
        self.approve_submission(submission.id)
        return submission

    @property
    def project(self):
        return self.store.projects[PROJECT_ID]
