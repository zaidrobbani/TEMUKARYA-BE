"""Fake repository in-memory untuk workflow, payments, submissions, reviews, notifications, admin finance."""

import io
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.modules.admin_finance.domain.entities import (
    AdminTransaction,
    AdminTransactionDetail,
    FinanceSummary,
    PaidRow,
    TransactionFilter,
)
from app.modules.admin_finance.domain.repositories import AdminFinanceRepository
from app.modules.notifications.domain.entities import Notification
from app.modules.notifications.domain.repositories import NotificationRepository
from app.modules.payments.domain.entities import (
    BalanceType,
    FundStatus,
    Payment,
    PaymentAttempt,
    PaymentHistoryItem,
    TransactionGroup,
    Wallet,
    WalletBalance,
    WalletEntry,
    WalletEntryFilter,
    WalletEntryType,
    WalletTransaction,
    WalletTransactionType,
)
from app.modules.payments.domain.repositories import PaymentRepository, WalletRepository
from app.modules.reviews.domain.entities import FreelancerReview, PublicReview, RatingSummary, ReviewerSummary
from app.modules.reviews.domain.repositories import ReviewRepository
from app.modules.submissions.domain.entities import Submission, SubmissionReview
from app.modules.submissions.domain.repositories import SubmissionFileStorage, SubmissionRepository
from app.modules.workflow.domain.entities import (
    Agreement,
    ApplicationSnapshot,
    MyProjectRow,
    Party,
    PaymentSnapshot,
    ProjectParties,
    StatusHistoryEntry,
    SubmissionSnapshot,
    UserSummary,
    WorkflowProject,
)
from app.modules.workflow.domain.repositories import WorkflowRepository

NOW = datetime(2026, 11, 10, 3, 0, tzinfo=UTC)  # 10.00 WIB
UMKM_ID = "umkm-1"
FREELANCER_ID = "freelancer-1"
OTHER_FREELANCER_ID = "freelancer-2"
OTHER_UMKM_ID = "umkm-2"
PROJECT_ID = "project-1"


class Clock:
    def __init__(self, now: datetime = NOW):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@dataclass
class Store:
    users: dict[str, dict] = field(default_factory=dict)
    projects: dict[str, WorkflowProject] = field(default_factory=dict)
    agreements: dict[str, Agreement] = field(default_factory=dict)
    history: list[StatusHistoryEntry] = field(default_factory=list)
    applications: dict[str, ApplicationSnapshot] = field(default_factory=dict)
    milestones: dict[str, list[tuple[Decimal, bool]]] = field(default_factory=dict)
    payments: dict[str, Payment] = field(default_factory=dict)
    attempts: list[PaymentAttempt] = field(default_factory=list)
    wallets: dict[str, Wallet] = field(default_factory=dict)
    wallet_txs: list[WalletTransaction] = field(default_factory=list)
    submissions: dict[str, Submission] = field(default_factory=dict)
    reviews: dict[str, FreelancerReview] = field(default_factory=dict)
    notifications: list[Notification] = field(default_factory=list)
    locks: list[str] = field(default_factory=list)

    def add_user(self, user_id: str, role: str, name: str, subtitle: str | None = None) -> None:
        self.users[user_id] = {"role": role, "name": name, "subtitle": subtitle}

    def add_project(self, project_id: str = PROJECT_ID, umkm_id: str = UMKM_ID, **overrides) -> WorkflowProject:
        project = WorkflowProject(
            id=project_id,
            umkm_id=umkm_id,
            category_id="graphic_design",
            title=overrides.pop("title", "Rebranding Pouch Kopi"),
            description="Desain logo dan kemasan pouch 250gr",
            budget=overrides.pop("budget", 1_500_000),
            deadline=overrides.pop("deadline", date(2026, 12, 1)),
            status=overrides.pop("status", "TERBUKA"),
            published_at=overrides.pop("published_at", NOW - timedelta(days=3)),
            created_at=NOW - timedelta(days=3),
            **overrides,
        )
        self.projects[project_id] = project
        return project

    def add_application(
        self, freelancer_id: str = FREELANCER_ID, project_id: str = PROJECT_ID, price: int = 1_500_000, days: int = 14
    ) -> ApplicationSnapshot:
        application = ApplicationSnapshot(
            id=f"app-{freelancer_id}-{project_id}",
            project_id=project_id,
            freelancer_id=freelancer_id,
            proposed_price=price,
            estimated_duration_days=days,
            status="SUBMITTED",
        )
        self.applications[application.id] = application
        return application

    def agreement_for(self, project_id: str = PROJECT_ID) -> Agreement | None:
        return next((a for a in self.agreements.values() if a.project_id == project_id), None)

    def payment_for(self, project_id: str = PROJECT_ID) -> Payment | None:
        agreement = self.agreement_for(project_id)
        return next((p for p in self.payments.values() if agreement and p.agreement_id == agreement.id), None)

    def notifications_for(self, user_id: str) -> list[Notification]:
        return [n for n in self.notifications if n.user_id == user_id]


def _summary(store: Store, user_id: str | None) -> UserSummary | None:
    if user_id is None:
        return None
    user = store.users.get(user_id, {"name": user_id, "subtitle": None})
    return UserSummary(id=user_id, name=user["name"], subtitle=user["subtitle"])


class FakeWorkflowRepository(WorkflowRepository):
    def __init__(self, store: Store):
        self.s = store

    def get_project(self, project_id, lock=False):
        if lock:
            self.s.locks.append(project_id)
        return self.s.projects.get(project_id)

    def set_project_status(self, project_id, status, started_at=None, completed_at=None):
        project = self.s.projects[project_id]
        self.s.projects[project_id] = replace(
            project,
            status=status,
            started_at=started_at or project.started_at,
            completed_at=completed_at or project.completed_at,
        )

    def add_history(self, entry):
        self.s.history.append(entry)

    def list_history(self, project_id):
        return [h for h in self.s.history if h.project_id == project_id]

    def get_agreement(self, project_id, lock=False):
        return self.s.agreement_for(project_id)

    def add_agreement(self, agreement):
        if self.s.agreement_for(agreement.project_id) is not None:
            raise AssertionError("UNIQUE(project_id) dilanggar")
        self.s.agreements[agreement.id] = agreement

    def update_agreement(self, agreement):
        self.s.agreements[agreement.id] = agreement

    def get_application(self, application_id):
        return self.s.applications.get(application_id)

    def find_application(self, project_id, freelancer_id):
        return next(
            (a for a in self.s.applications.values() if a.project_id == project_id and a.freelancer_id == freelancer_id),
            None,
        )

    def set_application_status(self, application_id, status):
        self.s.applications[application_id] = replace(self.s.applications[application_id], status=str(status))

    def close_submitted_applications(self, project_id, status):
        ids = []
        for app in list(self.s.applications.values()):
            if app.project_id == project_id and app.status == "SUBMITTED":
                self.s.applications[app.id] = replace(app, status=str(status))
                ids.append(app.freelancer_id)
        return ids

    def is_freelancer(self, user_id):
        return self.s.users.get(user_id, {}).get("role") == "FREELANCER"

    def get_parties(self, umkm_id, freelancer_id):
        return ProjectParties(umkm=_summary(self.s, umkm_id), freelancer=_summary(self.s, freelancer_id))

    def get_payment(self, agreement_id):
        payment = next((p for p in self.s.payments.values() if p.agreement_id == agreement_id), None)
        if payment is None:
            return None
        return PaymentSnapshot(
            id=payment.id,
            status=payment.status,
            fund_status=payment.fund_status,
            gross_amount=payment.gross_amount,
            platform_fee_amount=payment.platform_fee_amount,
            freelancer_amount=payment.freelancer_amount,
            transaction_number=payment.transaction_number,
            paid_at=payment.paid_at,
            released_at=payment.released_at,
            expires_at=payment.expires_at,
        )

    def latest_submission(self, project_id):
        items = sorted(
            (s for s in self.s.submissions.values() if s.project_id == project_id), key=lambda s: -s.version_number
        )
        if not items:
            return None
        latest = items[0]
        return SubmissionSnapshot(
            latest.id, latest.version_number, latest.submitted_at, latest.review.decision if latest.review else None
        )

    def count_revision_requests(self, project_id):
        return sum(
            1
            for s in self.s.submissions.values()
            if s.project_id == project_id and s.review and s.review.decision == "REVISION_REQUESTED"
        )

    def has_freelancer_review(self, project_id):
        return project_id in self.s.reviews

    def _mine(self, user_id, party):
        rows = []
        for project in self.s.projects.values():
            agreement = self.s.agreement_for(project.id)
            if party == Party.UMKM and project.umkm_id == user_id:
                rows.append((project, agreement))
            elif party == Party.FREELANCER and agreement and agreement.freelancer_id == user_id:
                rows.append((project, agreement))
        return rows

    def list_my_projects(self, user_id, party, status, limit, offset):
        result = []
        for project, agreement in self._mine(user_id, party):
            if status and project.status != status:
                continue
            counterpart_id = (agreement.freelancer_id if agreement else None) if party == Party.UMKM else project.umkm_id
            weights = self.s.milestones.get(project.id, [])
            result.append(
                MyProjectRow(
                    project=project,
                    agreement=agreement,
                    counterpart=_summary(self.s, counterpart_id),
                    payment=self.get_payment(agreement.id) if agreement else None,
                    application_count=sum(
                        1 for a in self.s.applications.values() if a.project_id == project.id and a.status == "SUBMITTED"
                    ),
                    progress_percent=float(sum(w for w, done in weights if done)) if weights else None,
                )
            )
        return result[offset: offset + limit]

    def count_my_projects_by_status(self, user_id, party):
        counts: dict[str, int] = {}
        for project, _ in self._mine(user_id, party):
            counts[project.status] = counts.get(project.status, 0) + 1
        return counts


class FakeMilestoneWeights:
    def __init__(self, store: Store):
        self.s = store

    def total_weight(self, project_id):
        return sum((w for w, _ in self.s.milestones.get(project_id, [])), Decimal("0.00"))


class FakePaymentRepository(PaymentRepository):
    def __init__(self, store: Store):
        self.s = store

    def get_by_agreement(self, agreement_id, lock=False):
        return next((p for p in self.s.payments.values() if p.agreement_id == agreement_id), None)

    def add(self, payment):
        self.s.payments[payment.id] = payment

    def update(self, payment):
        self.s.payments[payment.id] = payment

    def next_attempt_number(self, payment_id):
        return sum(1 for a in self.s.attempts if a.payment_id == payment_id) + 1

    def add_attempt(self, attempt):
        if attempt.idempotency_key and any(a.idempotency_key == attempt.idempotency_key for a in self.s.attempts):
            raise AssertionError("UNIQUE(idempotency_key) dilanggar")
        self.s.attempts.append(attempt)

    def get_attempt_by_key(self, idempotency_key):
        return next((a for a in self.s.attempts if a.idempotency_key == idempotency_key), None)

    def list_attempts(self, payment_id):
        return [a for a in self.s.attempts if a.payment_id == payment_id]

    def transaction_number_exists(self, number):
        return any(p.transaction_number == number for p in self.s.payments.values())

    def _history(self, umkm_id, search):
        rows = []
        for payment in self.s.payments.values():
            agreement = self.s.agreements[payment.agreement_id]
            project = self.s.projects[agreement.project_id]
            if project.umkm_id != umkm_id:
                continue
            name = self.s.users.get(agreement.freelancer_id, {}).get("name", agreement.freelancer_id)
            if search and search.lower() not in f"{project.title} {payment.transaction_number or ''} {name}".lower():
                continue
            rows.append(PaymentHistoryItem(payment, project.id, project.title, agreement.freelancer_id, name))
        return rows

    @staticmethod
    def _in_group(payment, group):
        return {
            TransactionGroup.ALL: True,
            TransactionGroup.PENDING: payment.status in ("MENUNGGU", "GAGAL"),
            TransactionGroup.HELD: payment.status == "BERHASIL" and payment.fund_status == "HELD",
            TransactionGroup.COMPLETED: payment.status == "BERHASIL" and payment.fund_status == "RELEASED",
            TransactionGroup.CANCELLED: payment.status == "DIBATALKAN",
        }[group]

    def list_umkm_history(self, umkm_id, group, search, limit, offset):
        rows = [r for r in self._history(umkm_id, search) if self._in_group(r.payment, group)]
        rows.sort(key=lambda r: r.payment.paid_at or r.payment.created_at, reverse=True)
        return rows[offset: offset + limit]

    def count_umkm_history(self, umkm_id, search):
        rows = self._history(umkm_id, search)
        return {g.value: sum(1 for r in rows if self._in_group(r.payment, g)) for g in TransactionGroup}


class FakeWalletRepository(WalletRepository):
    def __init__(self, store: Store):
        self.s = store

    def get_wallet(self, freelancer_id):
        return self.s.wallets.get(freelancer_id)

    def get_or_create_wallet(self, freelancer_id, now):
        return self.s.wallets.setdefault(freelancer_id, Wallet(str(uuid4()), freelancer_id))

    def add_transaction(self, transaction):
        key = (transaction.payment_id, transaction.transaction_type, transaction.balance_type)
        if any((t.payment_id, t.transaction_type, t.balance_type) == key for t in self.s.wallet_txs):
            raise AssertionError("UNIQUE(payment_id, transaction_type, balance_type) dilanggar")
        self.s.wallet_txs.append(transaction)

    def balance(self, wallet_id):
        txs = [t for t in self.s.wallet_txs if t.wallet_id == wallet_id]
        return WalletBalance(
            held=sum(t.amount_delta for t in txs if t.balance_type == BalanceType.HELD),
            available=sum(t.amount_delta for t in txs if t.balance_type == BalanceType.AVAILABLE),
        )

    def list_entries(self, wallet_id, entry_filter, limit, offset):
        entries = []
        for t in self.s.wallet_txs:
            if t.wallet_id != wallet_id:
                continue
            payment = self.s.payments[t.payment_id]
            project = self.s.projects[self.s.agreements[payment.agreement_id].project_id]
            held = t.transaction_type == WalletTransactionType.PAYMENT_HELD and t.balance_type == BalanceType.HELD
            income = t.transaction_type == WalletTransactionType.FUND_RELEASED and t.balance_type == BalanceType.AVAILABLE
            if entry_filter == WalletEntryFilter.HELD and not (held and payment.fund_status == FundStatus.HELD):
                continue
            if entry_filter == WalletEntryFilter.INCOME and not income:
                continue
            if not (held or income):
                continue
            entries.append(
                WalletEntry(
                    id=t.id,
                    entry_type=WalletEntryType.FUND_HELD if held else WalletEntryType.FUND_RELEASED,
                    payment_id=payment.id,
                    project_id=project.id,
                    project_title=project.title,
                    amount=t.amount_delta,
                    created_at=t.created_at,
                    still_held=payment.fund_status == FundStatus.HELD,
                )
            )
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[offset: offset + limit]


class FakeSubmissionRepository(SubmissionRepository):
    def __init__(self, store: Store):
        self.s = store

    def next_version(self, project_id):
        return max((s.version_number for s in self.s.submissions.values() if s.project_id == project_id), default=0) + 1

    def add(self, submission):
        self.s.submissions[submission.id] = submission

    def list_for_project(self, project_id):
        return sorted(
            (s for s in self.s.submissions.values() if s.project_id == project_id), key=lambda s: -s.version_number
        )

    def get(self, project_id, submission_id):
        submission = self.s.submissions.get(submission_id)
        return submission if submission and submission.project_id == project_id else None

    def latest(self, project_id):
        items = self.list_for_project(project_id)
        return items[0] if items else None

    def add_review(self, review: SubmissionReview):
        submission = self.s.submissions[review.submission_id]
        if submission.review is not None:
            raise AssertionError("UNIQUE(submission_id) dilanggar")
        self.s.submissions[submission.id] = replace(submission, review=review)


class FakeStorage(SubmissionFileStorage):
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.fail_on_save = False

    def save(self, source, extension):
        if self.fail_on_save:
            raise OSError("disk penuh")
        key = f"{uuid4().hex}.{extension}"
        source.seek(0)
        self.files[key] = source.read()
        return key

    def open(self, storage_key):
        return io.BytesIO(self.files[storage_key])

    def delete(self, storage_key):
        self.deleted.append(storage_key)
        self.files.pop(storage_key, None)


class FakeReviewRepository(ReviewRepository):
    def __init__(self, store: Store):
        self.s = store

    def get_by_project(self, project_id):
        return self.s.reviews.get(project_id)

    def add(self, review):
        if review.project_id in self.s.reviews:
            raise AssertionError("UNIQUE(project_id) dilanggar")
        self.s.reviews[review.project_id] = review

    def _for(self, freelancer_id):
        result = []
        for review in self.s.reviews.values():
            agreement = self.s.agreement_for(review.project_id)
            if agreement and agreement.freelancer_id == freelancer_id:
                project = self.s.projects[review.project_id]
                umkm = self.s.users.get(project.umkm_id, {"name": project.umkm_id, "subtitle": None})
                result.append(
                    PublicReview(
                        review, project.title, ReviewerSummary(project.umkm_id, umkm["name"], umkm["subtitle"], None)
                    )
                )
        return sorted(result, key=lambda r: r.review.created_at, reverse=True)

    def list_for_freelancer(self, freelancer_id, limit, offset):
        return self._for(freelancer_id)[offset: offset + limit]

    def summary_for_freelancer(self, freelancer_id):
        rows = self._for(freelancer_id)
        if not rows:
            return RatingSummary(None, 0)
        return RatingSummary(round(sum(r.review.rating for r in rows) / len(rows), 2), len(rows))


class FakeNotificationRepository(NotificationRepository):
    def __init__(self, store: Store):
        self.s = store

    def add(self, notification):
        self.s.notifications.append(notification)

    def list_for_user(self, user_id, types, unread_only, limit, offset):
        rows = [
            n
            for n in self.s.notifications
            if n.user_id == user_id
            and (types is None or n.notification_type in types)
            and (not unread_only or n.read_at is None)
        ]
        rows.sort(key=lambda n: n.created_at, reverse=True)
        return rows[offset: offset + limit]

    def count_by_type(self, user_id):
        counts: dict[str, int] = {}
        for n in self.s.notifications:
            if n.user_id == user_id:
                counts[n.notification_type] = counts.get(n.notification_type, 0) + 1
        return counts

    def count_unread(self, user_id):
        return sum(1 for n in self.s.notifications if n.user_id == user_id and n.read_at is None)

    def get(self, user_id, notification_id):
        return next((n for n in self.s.notifications if n.id == notification_id and n.user_id == user_id), None)

    def mark_read(self, user_id, notification_id, read_at):
        for i, n in enumerate(self.s.notifications):
            if n.id == notification_id and n.user_id == user_id and n.read_at is None:
                self.s.notifications[i] = replace(n, read_at=read_at)

    def mark_all_read(self, user_id, read_at):
        count = 0
        for i, n in enumerate(self.s.notifications):
            if n.user_id == user_id and n.read_at is None:
                self.s.notifications[i] = replace(n, read_at=read_at)
                count += 1
        return count


class FakeAdminFinanceRepository(AdminFinanceRepository):
    def __init__(self, store: Store):
        self.s = store

    def _rows(self) -> list[AdminTransaction]:
        rows = []
        for payment in self.s.payments.values():
            agreement = self.s.agreements[payment.agreement_id]
            project = self.s.projects[agreement.project_id]
            umkm = self.s.users.get(project.umkm_id, {"name": project.umkm_id, "subtitle": None})
            freelancer = self.s.users.get(agreement.freelancer_id, {"name": agreement.freelancer_id})
            rows.append(
                AdminTransaction(
                    payment, project.id, project.title, project.status, project.umkm_id, umkm["name"],
                    umkm["subtitle"], agreement.freelancer_id, freelancer["name"],
                )
            )
        return rows

    def _filter(self, f: TransactionFilter) -> list[AdminTransaction]:
        rows = []
        for r in self._rows():
            p = r.payment
            if f.status and p.status != f.status:
                continue
            if f.fund_status and p.fund_status != f.fund_status:
                continue
            if f.search and f.search.lower() not in f"{r.project_title} {p.transaction_number or ''} {r.umkm_name} {r.freelancer_name}".lower():
                continue
            if f.paid_from and (p.paid_at is None or p.paid_at < f.paid_from):
                continue
            if f.paid_to and (p.paid_at is None or p.paid_at >= f.paid_to):
                continue
            rows.append(r)
        return sorted(rows, key=lambda r: r.payment.paid_at or r.payment.created_at, reverse=True)

    def summary(self, month_start, month_end):
        ps = list(self.s.payments.values())
        ok = [p for p in ps if p.status == "BERHASIL"]
        return FinanceSummary(
            total_income=sum(p.platform_fee_amount for p in ok),
            income_this_month=sum(p.platform_fee_amount for p in ok if month_start <= p.paid_at < month_end),
            total_paid_amount=sum(p.gross_amount for p in ok),
            held_amount=sum(p.freelancer_amount for p in ps if p.fund_status == "HELD"),
            released_amount=sum(p.freelancer_amount for p in ps if p.fund_status == "RELEASED"),
            successful_transactions=len(ok),
            pending_transactions=sum(1 for p in ps if p.status == "MENUNGGU"),
            failed_transactions=sum(1 for p in ps if p.status == "GAGAL"),
            cancelled_transactions=sum(1 for p in ps if p.status == "DIBATALKAN"),
            total_transactions=len(ps),
        )

    def list_transactions(self, filters, limit, offset):
        return self._filter(filters)[offset: offset + limit]

    def count_transactions(self, filters):
        return len(self._filter(filters))

    def get_transaction(self, payment_id):
        row = next((r for r in self._rows() if r.payment.id == payment_id), None)
        if row is None:
            return None
        return AdminTransactionDetail(row, [a for a in self.s.attempts if a.payment_id == payment_id])

    def paid_rows(self, start, end):
        return [
            PaidRow(p.paid_at, p.platform_fee_amount, p.gross_amount)
            for p in self.s.payments.values()
            if p.status == "BERHASIL" and start <= p.paid_at < end
        ]
