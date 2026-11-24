import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import uuid4

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.unit_of_work import UnitOfWork
from app.modules.notifications.application.use_cases import Notifier
from app.modules.notifications.domain.entities import NotificationType, ReferenceType
from app.modules.payments.domain.entities import (
    QRIS_TTL,
    AttemptStatus,
    BalanceType,
    FundStatus,
    Payment,
    PaymentAttempt,
    PaymentHistoryItem,
    PaymentMethod,
    PaymentOutcome,
    PaymentStatus,
    TransactionGroup,
    WalletBalance,
    WalletEntry,
    WalletEntryFilter,
    WalletTransaction,
    WalletTransactionType,
    generate_transaction_number,
    split_amount,
)
from app.modules.payments.domain.repositories import PaymentRepository, WalletRepository
from app.modules.users.domain.entities import UserRole
from app.modules.workflow.application.dto import Actor
from app.modules.workflow.application.services import (
    Clock,
    ProjectAccess,
    ProjectContext,
    change_status,
    utc_now,
)
from app.modules.workflow.domain.entities import (
    Agreement,
    ChangeSource,
    Party,
    ProjectParties,
    ProjectStatus,
    WorkflowAction,
    WorkflowProject,
)
from app.modules.workflow.domain.repositories import PaymentPort, WorkflowRepository

MAX_PAGE_LIMIT = 100
MAX_SEARCH_LENGTH = 100
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_\-:.]{8,64}$")
NumberGenerator = Callable[[datetime], str]


def rupiah(amount: int) -> str:
    return "Rp" + f"{amount:,}".replace(",", ".")


def _conflict(message: str, code: str) -> ConflictError:
    error = ConflictError(message)
    error.code = code
    return error


def _validate_page(limit: int, offset: int) -> None:
    if not 1 <= limit <= MAX_PAGE_LIMIT:
        raise BadRequestError(f"Limit harus 1 sampai {MAX_PAGE_LIMIT}")
    if offset < 0:
        raise BadRequestError("Offset tidak boleh negatif")


@dataclass(frozen=True)
class PaymentDetail:
    payment: Payment
    project: WorkflowProject
    agreement: Agreement
    parties: ProjectParties
    attempts: list[PaymentAttempt]
    now: datetime


@dataclass(frozen=True)
class SimulationResult:
    detail: PaymentDetail
    attempt: PaymentAttempt | None
    already_paid: bool = False
    replayed: bool = False


@dataclass(frozen=True)
class PaymentHistoryPage:
    items: list[PaymentHistoryItem]
    has_more: bool
    counts: dict[str, int]


@dataclass(frozen=True)
class WalletEntriesPage:
    items: list[WalletEntry]
    has_more: bool


class PaymentService(PaymentPort):
    """Implementasi PaymentPort untuk workflow. Tidak commit: ikut transaksi pemanggil."""

    def __init__(self, payments: PaymentRepository):
        self._payments = payments

    def create_invoice(self, agreement: Agreement, now: datetime) -> None:
        fee, net = split_amount(agreement.agreed_price)
        existing = self._payments.get_by_agreement(agreement.id, lock=True)
        if existing is None:
            self._payments.add(
                Payment(
                    id=str(uuid4()),
                    agreement_id=agreement.id,
                    gross_amount=agreement.agreed_price,
                    platform_fee_amount=fee,
                    freelancer_amount=net,
                    payment_method=PaymentMethod.QRIS_SIMULATION.value,
                    status=PaymentStatus.MENUNGGU.value,
                    created_at=now,
                    expires_at=now + QRIS_TTL,
                    updated_at=now,
                )
            )
            return
        if existing.status == PaymentStatus.BERHASIL:
            raise ConflictError("Pembayaran proyek ini sudah berhasil")
        # Tagihan yang belum berhasil mengikuti nilai kesepakatan terbaru.
        self._payments.update(
            replace(
                existing,
                gross_amount=agreement.agreed_price,
                platform_fee_amount=fee,
                freelancer_amount=net,
                status=PaymentStatus.MENUNGGU.value,
                expires_at=now + QRIS_TTL,
                updated_at=now,
            )
        )

    def cancel_open_invoice(self, agreement_id: str, now: datetime) -> None:
        payment = self._payments.get_by_agreement(agreement_id, lock=True)
        if payment is None:
            return
        if payment.status == PaymentStatus.BERHASIL:
            raise ConflictError("Proyek tidak dapat dibatalkan setelah pembayaran berhasil")
        if payment.status != PaymentStatus.DIBATALKAN:
            self._payments.update(
                replace(payment, status=PaymentStatus.DIBATALKAN.value, expires_at=None, updated_at=now)
            )


class FundReleaser:
    """Pelepasan dana HELD → RELEASED. Dipanggil saat UMKM menyetujui hasil, dalam transaksi yang sama."""

    def __init__(self, payments: PaymentRepository, wallets: WalletRepository):
        self._payments = payments
        self._wallets = wallets

    def current(self, agreement: Agreement) -> Payment:
        payment = self._payments.get_by_agreement(agreement.id)
        if payment is None:
            raise NotFoundError("Tagihan pembayaran tidak ditemukan")
        return payment

    def release(self, agreement: Agreement, project_title: str, now: datetime) -> Payment:
        payment = self._payments.get_by_agreement(agreement.id, lock=True)
        if payment is None or payment.status != PaymentStatus.BERHASIL:
            raise ConflictError("Pembayaran proyek belum berhasil")
        if payment.fund_status == FundStatus.RELEASED:
            return payment
        if payment.fund_status != FundStatus.HELD:
            raise ConflictError("Dana proyek tidak dalam status ditahan")

        wallet = self._wallets.get_or_create_wallet(agreement.freelancer_id, now)
        for balance_type, delta in ((BalanceType.HELD, -payment.freelancer_amount),
                                    (BalanceType.AVAILABLE, payment.freelancer_amount)):
            self._wallets.add_transaction(
                WalletTransaction(
                    id=str(uuid4()),
                    wallet_id=wallet.id,
                    payment_id=payment.id,
                    transaction_type=WalletTransactionType.FUND_RELEASED.value,
                    balance_type=balance_type.value,
                    amount_delta=delta,
                    created_at=now,
                    description=f"Pemasukan project: {project_title}"[:400],
                )
            )
        released = replace(payment, fund_status=FundStatus.RELEASED.value, released_at=now, updated_at=now)
        self._payments.update(released)
        return released


class _PaymentUseCase:
    def __init__(self, workflow: WorkflowRepository, payments: PaymentRepository, clock: Clock = utc_now):
        self._workflow = workflow
        self._payments = payments
        self._clock = clock
        self._access = ProjectAccess(workflow)

    def _detail(self, context: ProjectContext, payment: Payment) -> PaymentDetail:
        return PaymentDetail(
            payment=payment,
            project=context.project,
            agreement=context.agreement,
            parties=self._workflow.get_parties(context.project.umkm_id, context.agreement.freelancer_id),
            attempts=self._payments.list_attempts(payment.id),
            now=self._clock(),
        )

    def _load_payment(self, actor: Actor, project_id: str, lock: bool = False) -> tuple[ProjectContext, Payment]:
        context = self._access.load(project_id, actor, lock=lock)
        payment = None
        if context.agreement is not None:
            payment = self._payments.get_by_agreement(context.agreement.id, lock=lock)
        if payment is None:
            raise NotFoundError("Tagihan pembayaran belum tersedia, kesepakatan belum final")
        return context, payment


class GetProjectPayment(_PaymentUseCase):
    """U-18/U-20/U-21: detail tagihan, status, dan bukti pembayaran."""

    def execute(self, actor: Actor, project_id: str) -> PaymentDetail:
        context, payment = self._load_payment(actor, project_id)
        return self._detail(context, payment)


class RefreshQris(_PaymentUseCase):
    """Buat ulang QRIS (simulasi diulang): status kembali MENUNGGU dengan masa berlaku baru."""

    def __init__(
        self, workflow: WorkflowRepository, payments: PaymentRepository, uow: UnitOfWork, clock: Clock = utc_now
    ):
        super().__init__(workflow, payments, clock)
        self._uow = uow

    def execute(self, actor: Actor, project_id: str) -> PaymentDetail:
        context, payment = self._load_payment(actor, project_id, lock=True)
        if context.party != Party.UMKM:
            raise ForbiddenError("Hanya UMKM pemilik yang dapat membayar proyek")
        _ensure_payable(context, payment)
        now = self._clock()
        payment = replace(payment, status=PaymentStatus.MENUNGGU.value, expires_at=now + QRIS_TTL, updated_at=now)
        self._payments.update(payment)
        self._uow.commit()
        return self._detail(context, payment)


def _ensure_payable(context: ProjectContext, payment: Payment) -> None:
    if payment.status == PaymentStatus.BERHASIL:
        raise _conflict("Pembayaran proyek ini sudah berhasil", "PAYMENT_ALREADY_PAID")
    if context.project.status == ProjectStatus.DIBATALKAN or payment.status == PaymentStatus.DIBATALKAN:
        raise ConflictError("Proyek sudah dibatalkan, tagihan tidak dapat dibayar")
    if context.project.status != ProjectStatus.MENUNGGU_PEMBAYARAN:
        raise ConflictError("Proyek tidak sedang menunggu pembayaran")


class SimulatePayment(_PaymentUseCase):
    """U-19: bayar (simulasi). Berhasil → dana HELD + project Siap Dikerjakan dalam satu transaksi."""

    def __init__(
        self,
        workflow: WorkflowRepository,
        payments: PaymentRepository,
        wallets: WalletRepository,
        notifier: Notifier,
        uow: UnitOfWork,
        clock: Clock = utc_now,
        number_generator: NumberGenerator = generate_transaction_number,
    ):
        super().__init__(workflow, payments, clock)
        self._wallets = wallets
        self._notifier = notifier
        self._uow = uow
        self._number_generator = number_generator

    def execute(
        self,
        actor: Actor,
        project_id: str,
        outcome: PaymentOutcome = PaymentOutcome.SUCCESS,
        idempotency_key: str | None = None,
    ) -> SimulationResult:
        if idempotency_key is not None and not _IDEMPOTENCY_KEY.fullmatch(idempotency_key):
            raise BadRequestError("Idempotency-Key harus 8-64 karakter huruf, angka, '-', '_', ':', atau '.'")
        try:
            outcome = PaymentOutcome(outcome)
        except ValueError:
            raise BadRequestError("Hasil simulasi harus SUCCESS atau FAILED") from None

        context, payment = self._load_payment(actor, project_id, lock=True)
        if context.party != Party.UMKM:
            raise ForbiddenError("Hanya UMKM pemilik yang dapat membayar proyek")

        if idempotency_key is not None:
            previous = self._payments.get_attempt_by_key(idempotency_key)
            if previous is not None:
                if previous.payment_id != payment.id:
                    raise ConflictError("Idempotency-Key sudah dipakai untuk pembayaran lain")
                return SimulationResult(self._detail(context, payment), previous, replayed=True)

        # Pembayaran ganda: kembalikan data sebelumnya tanpa transaksi baru.
        if payment.status == PaymentStatus.BERHASIL:
            return SimulationResult(self._detail(context, payment), None, already_paid=True)
        _ensure_payable(context, payment)
        if payment.status == PaymentStatus.GAGAL:
            raise _conflict(
                "Pembayaran sebelumnya gagal, buat ulang QRIS untuk mencoba lagi", "QRIS_REFRESH_REQUIRED"
            )
        now = self._clock()
        if payment.is_expired(now):
            raise _conflict("QRIS sudah kedaluwarsa, buat ulang QRIS untuk membayar", "QRIS_EXPIRED")

        attempt = PaymentAttempt(
            id=str(uuid4()),
            payment_id=payment.id,
            attempt_number=self._payments.next_attempt_number(payment.id),
            status=(AttemptStatus.SUCCEEDED if outcome == PaymentOutcome.SUCCESS else AttemptStatus.FAILED).value,
            attempted_at=now,
            idempotency_key=idempotency_key,
            failure_reason=None if outcome == PaymentOutcome.SUCCESS else "Simulasi pembayaran gagal",
            completed_at=now,
        )
        self._payments.add_attempt(attempt)

        if outcome == PaymentOutcome.FAILED:
            payment = replace(payment, status=PaymentStatus.GAGAL.value, updated_at=now)
            self._payments.update(payment)
            self._notifier.notify(
                context.project.umkm_id,
                NotificationType.PAYMENT_FAILED,
                "Pembayaran gagal",
                f"Pembayaran {context.project.title} gagal, silakan coba lagi",
                ReferenceType.PROJECT,
                project_id,
            )
            self._uow.commit()
            return SimulationResult(self._detail(context, payment), attempt)

        payment = replace(
            payment,
            status=PaymentStatus.BERHASIL.value,
            fund_status=FundStatus.HELD.value,
            paid_at=now,
            transaction_number=self._unique_number(now),
            updated_at=now,
        )
        self._payments.update(payment)
        wallet = self._wallets.get_or_create_wallet(context.agreement.freelancer_id, now)
        self._wallets.add_transaction(
            WalletTransaction(
                id=str(uuid4()),
                wallet_id=wallet.id,
                payment_id=payment.id,
                transaction_type=WalletTransactionType.PAYMENT_HELD.value,
                balance_type=BalanceType.HELD.value,
                amount_delta=payment.freelancer_amount,
                created_at=now,
                description=f"Dana ditahan: {context.project.title}"[:400],
            )
        )
        project = change_status(
            self._workflow,
            context.project,
            ProjectStatus.SIAP_DIKERJAKAN,
            WorkflowAction.PAYMENT_SUCCEEDED,
            actor.user_id,
            now,
            source=ChangeSource.SYSTEM,
        )
        context = ProjectContext(project, context.agreement, context.party)
        self._notifier.notify(
            project.umkm_id,
            NotificationType.PAYMENT_SUCCEEDED,
            "Pembayaran berhasil",
            f"{rupiah(payment.gross_amount)} ditahan TEMUKARYA sampai hasil disetujui",
            ReferenceType.PROJECT,
            project_id,
        )
        self._notifier.notify(
            context.agreement.freelancer_id,
            NotificationType.PAYMENT_RECEIVED,
            "Pembayaran diterima",
            f"Dana {rupiah(payment.freelancer_amount)} ditahan TEMUKARYA. Kamu bisa mulai mengerjakan {project.title}",
            ReferenceType.PROJECT,
            project_id,
        )
        self._uow.commit()
        return SimulationResult(self._detail(context, payment), attempt)

    def _unique_number(self, now: datetime) -> str:
        for _ in range(10):
            number = self._number_generator(now)
            if not self._payments.transaction_number_exists(number):
                return number
        raise ConflictError("Gagal membuat nomor transaksi, silakan coba lagi")


class ListPaymentHistory:
    """U-22: riwayat transaksi UMKM."""

    def __init__(self, payments: PaymentRepository):
        self._payments = payments

    def execute(
        self,
        actor: Actor,
        group: TransactionGroup = TransactionGroup.ALL,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> PaymentHistoryPage:
        if actor.role != UserRole.UMKM:
            raise ForbiddenError("Riwayat transaksi hanya untuk UMKM")
        _validate_page(limit, offset)
        search = (search or "").strip() or None
        if search is not None and len(search) > MAX_SEARCH_LENGTH:
            raise BadRequestError(f"Kata kunci maksimal {MAX_SEARCH_LENGTH} karakter")
        rows = self._payments.list_umkm_history(actor.user_id, TransactionGroup(group), search, limit + 1, offset)
        counts = self._payments.count_umkm_history(actor.user_id, search)
        return PaymentHistoryPage(rows[:limit], len(rows) > limit, counts)


class GetWallet:
    """F-20: saldo tersedia, tertahan, dan total."""

    def __init__(self, wallets: WalletRepository):
        self._wallets = wallets

    def execute(self, actor: Actor) -> WalletBalance:
        if actor.role != UserRole.FREELANCER:
            raise ForbiddenError("Dompet hanya untuk freelancer")
        wallet = self._wallets.get_wallet(actor.user_id)
        return self._wallets.balance(wallet.id) if wallet else WalletBalance()


class ListWalletEntries:
    """F-24: riwayat dana masuk freelancer."""

    def __init__(self, wallets: WalletRepository):
        self._wallets = wallets

    def execute(
        self,
        actor: Actor,
        entry_filter: WalletEntryFilter = WalletEntryFilter.ALL,
        limit: int = 20,
        offset: int = 0,
    ) -> WalletEntriesPage:
        if actor.role != UserRole.FREELANCER:
            raise ForbiddenError("Dompet hanya untuk freelancer")
        _validate_page(limit, offset)
        wallet = self._wallets.get_wallet(actor.user_id)
        if wallet is None:
            return WalletEntriesPage([], False)
        rows = self._wallets.list_entries(wallet.id, WalletEntryFilter(entry_filter), limit + 1, offset)
        return WalletEntriesPage(rows[:limit], len(rows) > limit)
