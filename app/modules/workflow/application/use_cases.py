from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.unit_of_work import UnitOfWork
from app.modules.applications.domain.entities import ApplicationStatus
from app.modules.notifications.application.use_cases import Notifier
from app.modules.notifications.domain.entities import NotificationType, ReferenceType
from app.modules.users.domain.entities import UserRole
from app.modules.workflow.application.dto import (
    Actor,
    CancelProjectInput,
    MyProjectsPage,
    SelectFreelancerInput,
    UpdateAgreementInput,
    WorkflowDetail,
)
from app.modules.workflow.application.services import (
    PROJECT_NOT_FOUND,
    Clock,
    ProjectAccess,
    ProjectContext,
    build_detail,
    change_status,
    utc_now,
)
from app.modules.workflow.domain.entities import (
    CANCEL_REASON_LABELS,
    Agreement,
    AgreementStatus,
    CancelReason,
    Party,
    ProjectStatus,
    SelectionSource,
    WorkflowAction,
    wib_date,
)
from app.modules.workflow.domain.repositories import MilestoneWeightReader, PaymentPort, WorkflowRepository
from app.modules.workflow.domain.rules import cancel_blocker, start_blocker

MAX_PRICE = 1_000_000_000_000
MAX_DURATION_DAYS = 365
MAX_SCOPE_LENGTH = 5000
MAX_NOTE_LENGTH = 2000
MAX_CANCEL_NOTE_LENGTH = 500
REQUIRED_TOTAL_WEIGHT = Decimal("100")
MAX_PAGE_LIMIT = 100


def _rupiah(amount: int) -> str:
    return "Rp" + f"{amount:,}".replace(",", ".")


def _other_party_user(context: ProjectContext) -> str | None:
    if context.party == Party.UMKM:
        return context.agreement.freelancer_id if context.agreement else None
    return context.project.umkm_id


def _party_name(repository: WorkflowRepository, context: ProjectContext) -> str:
    parties = repository.get_parties(
        context.project.umkm_id, context.agreement.freelancer_id if context.agreement else None
    )
    if context.party == Party.UMKM:
        return parties.umkm.subtitle or parties.umkm.name
    return parties.freelancer.name if parties.freelancer else "Freelancer"


class GetProjectWorkflow:
    def __init__(self, repository: WorkflowRepository):
        self._repository = repository
        self._access = ProjectAccess(repository)

    def execute(self, actor: Actor, project_id: str) -> WorkflowDetail:
        return build_detail(self._repository, self._access.load(project_id, actor))


class SelectFreelancer:
    """U-12: UMKM memilih freelancer → Menunggu Kesepakatan."""

    def __init__(
        self,
        repository: WorkflowRepository,
        notifier: Notifier,
        uow: UnitOfWork,
        clock: Clock = utc_now,
    ):
        self._repository = repository
        self._notifier = notifier
        self._uow = uow
        self._clock = clock

    def execute(self, actor: Actor, project_id: str, data: SelectFreelancerInput) -> WorkflowDetail:
        if actor.role != UserRole.UMKM:
            raise ForbiddenError("Hanya UMKM yang dapat memilih freelancer")
        if (data.application_id is None) == (data.freelancer_id is None):
            raise BadRequestError("Isi salah satu: application_id atau freelancer_id")

        project = self._repository.get_project(project_id, lock=True)
        if project is None or project.umkm_id != actor.user_id:
            raise NotFoundError(PROJECT_NOT_FOUND)
        if project.status != ProjectStatus.TERBUKA:
            if self._repository.get_agreement(project_id) is not None:
                raise ConflictError("Proyek sudah memiliki freelancer terpilih")
            raise ConflictError("Freelancer hanya dapat dipilih saat proyek berstatus Terbuka")
        if project.published_at is None:
            raise ConflictError("Proyek belum dipublikasikan")

        now = self._clock()
        today = wib_date(now)
        application = self._resolve_application(project_id, data)

        if application is not None:
            freelancer_id = application.freelancer_id
            price = application.proposed_price
            deadline = today + timedelta(days=application.estimated_duration_days)
            source = SelectionSource.APPLICATION
        else:
            freelancer_id = data.freelancer_id
            price = project.budget
            deadline = project.deadline
            source = SelectionSource.DIRECT
            if deadline <= today:
                raise BadRequestError(
                    "Deadline proyek sudah lewat, perbarui deadline proyek sebelum memilih freelancer"
                )

        scope = (data.scope_of_work or "").strip() or project.description.strip()
        if len(scope) > MAX_SCOPE_LENGTH:
            raise BadRequestError(f"Lingkup pekerjaan maksimal {MAX_SCOPE_LENGTH} karakter")

        agreement = Agreement(
            id=str(uuid4()),
            project_id=project_id,
            freelancer_id=freelancer_id,
            application_id=application.id if application else None,
            selection_source=source.value,
            scope_of_work=scope,
            agreed_price=price,
            agreed_deadline=deadline,
            status=AgreementStatus.PENDING_APPROVAL.value,
            agreement_version=1,
            created_at=now,
            updated_at=now,
        )
        self._repository.add_agreement(agreement)
        if application is not None:
            self._repository.set_application_status(application.id, ApplicationStatus.ACCEPTED)
        not_selected = self._repository.close_submitted_applications(project_id, ApplicationStatus.NOT_SELECTED)
        project = change_status(
            self._repository,
            project,
            ProjectStatus.MENUNGGU_KESEPAKATAN,
            WorkflowAction.SELECT_FREELANCER,
            actor.user_id,
            now,
        )

        context = ProjectContext(project, agreement, Party.UMKM)
        umkm_name = _party_name(self._repository, context)
        self._notifier.notify(
            freelancer_id,
            NotificationType.APPLICATION_ACCEPTED,
            "Pengajuanmu disetujui!",
            f"{umkm_name} mengajak negosiasi untuk {project.title}",
            ReferenceType.PROJECT,
            project_id,
        )
        for other_id in not_selected:
            self._notifier.notify(
                other_id,
                NotificationType.APPLICATION_NOT_SELECTED,
                "Pengajuan tidak dipilih",
                f"{project.title} sudah memilih freelancer lain",
                ReferenceType.PROJECT,
                project_id,
            )
        self._uow.commit()
        return build_detail(self._repository, context)

    def _resolve_application(self, project_id: str, data: SelectFreelancerInput):
        if data.application_id is not None:
            application = self._repository.get_application(data.application_id)
            if application is None or application.project_id != project_id:
                raise NotFoundError("Pengajuan tidak ditemukan")
            if application.status != ApplicationStatus.SUBMITTED:
                raise ConflictError("Pengajuan ini sudah tidak aktif")
            return application

        if not self._repository.is_freelancer(data.freelancer_id):
            raise NotFoundError("Freelancer tidak ditemukan")
        application = self._repository.find_application(project_id, data.freelancer_id)
        if application is not None and application.status != ApplicationStatus.SUBMITTED:
            raise ConflictError("Pengajuan freelancer ini sudah tidak aktif")
        # Freelancer yang sudah melamar tetap dicatat lewat lamarannya.
        return application


class _AgreementUseCase:
    def __init__(
        self,
        repository: WorkflowRepository,
        notifier: Notifier,
        uow: UnitOfWork,
        clock: Clock = utc_now,
    ):
        self._repository = repository
        self._notifier = notifier
        self._uow = uow
        self._clock = clock
        self._access = ProjectAccess(repository)

    def _load_negotiation(self, actor: Actor, project_id: str) -> ProjectContext:
        context = self._access.load(project_id, actor, lock=True)
        if context.agreement is None:
            raise NotFoundError("Kesepakatan belum dibuat")
        if context.project.status != ProjectStatus.MENUNGGU_KESEPAKATAN:
            raise ConflictError(_negotiation_closed_message(context.project.status))
        return context

    def _notify_other(self, context: ProjectContext, type_: NotificationType, title: str, body: str) -> None:
        other = _other_party_user(context)
        if other is not None:
            self._notifier.notify(other, type_, title, body, ReferenceType.PROJECT, context.project.id)


def _negotiation_closed_message(status: str) -> str:
    if status == ProjectStatus.DIBATALKAN:
        return "Proyek sudah dibatalkan"
    return "Kesepakatan sudah final dan tidak dapat diubah"


class GetAgreement:
    def __init__(self, repository: WorkflowRepository):
        self._repository = repository
        self._access = ProjectAccess(repository)

    def execute(self, actor: Actor, project_id: str) -> WorkflowDetail:
        context = self._access.load(project_id, actor)
        if context.agreement is None:
            raise NotFoundError("Kesepakatan belum dibuat")
        return build_detail(self._repository, context)


class UpdateAgreement(_AgreementUseCase):
    """Perubahan detail sebelum pembayaran membatalkan kedua persetujuan."""

    def execute(self, actor: Actor, project_id: str, data: UpdateAgreementInput) -> WorkflowDetail:
        if all(v is None for v in (data.scope_of_work, data.agreed_price, data.agreed_deadline, data.duration_days)):
            raise BadRequestError("Tidak ada perubahan kesepakatan yang dikirim")
        if data.agreed_deadline is not None and data.duration_days is not None:
            raise BadRequestError("Isi salah satu: agreed_deadline atau duration_days")

        context = self._load_negotiation(actor, project_id)
        agreement = context.agreement
        now = self._clock()

        scope = agreement.scope_of_work
        if data.scope_of_work is not None:
            scope = data.scope_of_work.strip()
            if not scope:
                raise BadRequestError("Lingkup pekerjaan wajib diisi")
            if len(scope) > MAX_SCOPE_LENGTH:
                raise BadRequestError(f"Lingkup pekerjaan maksimal {MAX_SCOPE_LENGTH} karakter")

        price = agreement.agreed_price
        if data.agreed_price is not None:
            if type(data.agreed_price) is not int or not 1 <= data.agreed_price <= MAX_PRICE:
                raise BadRequestError("Nilai proyek harus bilangan bulat lebih dari nol")
            price = data.agreed_price

        deadline = agreement.agreed_deadline
        if data.duration_days is not None:
            if type(data.duration_days) is not int or not 1 <= data.duration_days <= MAX_DURATION_DAYS:
                raise BadRequestError(f"Durasi pengerjaan harus 1 sampai {MAX_DURATION_DAYS} hari")
            deadline = wib_date(agreement.created_at) + timedelta(days=data.duration_days)
        if data.agreed_deadline is not None:
            deadline = data.agreed_deadline
        if deadline != agreement.agreed_deadline and deadline <= wib_date(now):
            raise BadRequestError("Deadline harus setelah hari ini")
        if (deadline - wib_date(agreement.created_at)).days > MAX_DURATION_DAYS:
            raise BadRequestError(f"Durasi pengerjaan maksimal {MAX_DURATION_DAYS} hari")

        if (scope, price, deadline) == (agreement.scope_of_work, agreement.agreed_price, agreement.agreed_deadline):
            return build_detail(self._repository, context)

        updated = replace(
            agreement,
            scope_of_work=scope,
            agreed_price=price,
            agreed_deadline=deadline,
            agreement_version=agreement.agreement_version + 1,
            umkm_approved_at=None,
            freelancer_approved_at=None,
            updated_at=now,
        )
        self._repository.update_agreement(updated)
        context = replace(context, agreement=updated)
        self._notify_other(
            context,
            NotificationType.AGREEMENT_UPDATED,
            "Kesepakatan diperbarui",
            f"Detail kesepakatan {context.project.title} berubah, periksa lalu tekan Lanjut Project lagi",
        )
        self._uow.commit()
        return build_detail(self._repository, context)


class ApproveAgreement(_AgreementUseCase):
    """U-15/F-15 Lanjut Project. Kedua pihak setuju → Menunggu Pembayaran + tagihan dibuat."""

    def __init__(
        self,
        repository: WorkflowRepository,
        milestones: MilestoneWeightReader,
        payments: PaymentPort,
        notifier: Notifier,
        uow: UnitOfWork,
        clock: Clock = utc_now,
    ):
        super().__init__(repository, notifier, uow, clock)
        self._milestones = milestones
        self._payments = payments

    def execute(self, actor: Actor, project_id: str, agreement_version: int | None = None) -> WorkflowDetail:
        context = self._access.load(project_id, actor, lock=True)
        agreement = context.agreement
        if agreement is None:
            raise NotFoundError("Kesepakatan belum dibuat")
        # Klik ulang setelah final tidak mengubah apa pun.
        if agreement.status == AgreementStatus.APPROVED:
            return build_detail(self._repository, context)
        if context.project.status != ProjectStatus.MENUNGGU_KESEPAKATAN:
            raise ConflictError(_negotiation_closed_message(context.project.status))
        if agreement_version is not None and agreement_version != agreement.agreement_version:
            error = ConflictError("Detail kesepakatan sudah berubah, muat ulang sebelum menyetujui")
            error.code = "AGREEMENT_CHANGED"
            raise error
        if agreement.approved_at(context.party) is not None:
            return build_detail(self._repository, context)

        total = self._milestones.total_weight(project_id)
        if total != REQUIRED_TOTAL_WEIGHT:
            error = ConflictError(
                f"Total bobot rencana pengerjaan harus 100% sebelum melanjutkan project (saat ini {total.normalize():f}%)"
            )
            error.code = "MILESTONE_PLAN_INCOMPLETE"
            raise error

        now = self._clock()
        approval = {"umkm_approved_at": now} if context.party == Party.UMKM else {"freelancer_approved_at": now}
        updated = replace(agreement, updated_at=now, **approval)

        if not updated.both_approved:
            self._repository.update_agreement(updated)
            context = replace(context, agreement=updated)
            name = _party_name(self._repository, context)
            self._notify_other(
                context,
                NotificationType.AGREEMENT_APPROVED,
                f"{name} menekan Lanjut Project",
                f"Periksa kesepakatan dan rencana pengerjaan {context.project.title}, lalu lanjutkan",
            )
            self._uow.commit()
            return build_detail(self._repository, context)

        updated = replace(updated, status=AgreementStatus.APPROVED.value)
        self._repository.update_agreement(updated)
        project = change_status(
            self._repository,
            context.project,
            ProjectStatus.MENUNGGU_PEMBAYARAN,
            WorkflowAction.APPROVE_AGREEMENT,
            actor.user_id,
            now,
        )
        self._payments.create_invoice(updated, now)
        context = ProjectContext(project, updated, context.party)
        for user_id, body in (
            (project.umkm_id, f"Lakukan pembayaran {_rupiah(updated.agreed_price)} untuk memulai {project.title}"),
            (updated.freelancer_id, f"Menunggu pembayaran UMKM untuk {project.title}"),
        ):
            self._notifier.notify(
                user_id,
                NotificationType.AGREEMENT_FINALIZED,
                "Kesepakatan final",
                body,
                ReferenceType.PROJECT,
                project.id,
            )
        self._uow.commit()
        return build_detail(self._repository, context)


class RequestAgreementChanges(_AgreementUseCase):
    """UMKM "Minta Ubah" rencana: persetujuan direset dan freelancer diberi tahu."""

    def execute(self, actor: Actor, project_id: str, note: str) -> WorkflowDetail:
        context = self._load_negotiation(actor, project_id)
        if context.party != Party.UMKM:
            raise ForbiddenError("Hanya UMKM pemilik yang dapat meminta perubahan rencana")
        note = (note or "").strip()
        if not note:
            raise BadRequestError("Catatan perubahan wajib diisi")
        if len(note) > MAX_NOTE_LENGTH:
            raise BadRequestError(f"Catatan perubahan maksimal {MAX_NOTE_LENGTH} karakter")

        now = self._clock()
        updated = replace(
            context.agreement,
            umkm_approved_at=None,
            freelancer_approved_at=None,
            change_request_note=note,
            change_requested_at=now,
            updated_at=now,
        )
        self._repository.update_agreement(updated)
        context = replace(context, agreement=updated)
        self._notify_other(
            context,
            NotificationType.AGREEMENT_CHANGES_REQUESTED,
            "UMKM meminta perubahan rencana",
            note,
        )
        self._uow.commit()
        return build_detail(self._repository, context)


class CancelProject:
    """U-16/F-16: batal hanya sebelum pembayaran berhasil."""

    def __init__(
        self,
        repository: WorkflowRepository,
        payments: PaymentPort,
        notifier: Notifier,
        uow: UnitOfWork,
        clock: Clock = utc_now,
    ):
        self._repository = repository
        self._payments = payments
        self._notifier = notifier
        self._uow = uow
        self._clock = clock
        self._access = ProjectAccess(repository)

    def execute(self, actor: Actor, project_id: str, data: CancelProjectInput) -> WorkflowDetail:
        try:
            reason = CancelReason(data.reason)
        except ValueError:
            raise BadRequestError("Alasan pembatalan tidak valid") from None
        note = (data.note or "").strip() or None
        if reason == CancelReason.LAINNYA and note is None:
            raise BadRequestError("Tuliskan alasan pembatalan")
        if note is not None and len(note) > MAX_CANCEL_NOTE_LENGTH:
            raise BadRequestError(f"Catatan pembatalan maksimal {MAX_CANCEL_NOTE_LENGTH} karakter")

        context = self._access.load(project_id, actor, lock=True)
        blocker = cancel_blocker(context.project.status, context.party)
        if blocker is not None:
            raise ConflictError(blocker)
        agreement = context.agreement
        payment = self._repository.get_payment(agreement.id) if agreement else None
        if payment is not None and payment.status == "BERHASIL":
            raise ConflictError("Proyek tidak dapat dibatalkan setelah pembayaran berhasil")

        now = self._clock()
        if agreement is not None:
            agreement = replace(agreement, status=AgreementStatus.CANCELLED.value, updated_at=now)
            self._repository.update_agreement(agreement)
            self._payments.cancel_open_invoice(agreement.id, now)
            if agreement.application_id is not None:
                self._repository.set_application_status(agreement.application_id, ApplicationStatus.CANCELLED)
        applicants = self._repository.close_submitted_applications(project_id, ApplicationStatus.CANCELLED)

        project = change_status(
            self._repository,
            context.project,
            ProjectStatus.DIBATALKAN,
            WorkflowAction.CANCEL_PROJECT,
            actor.user_id,
            now,
            reason=note,
            reason_code=reason.value,
        )
        context = ProjectContext(project, agreement, context.party)
        body = f"{project.title} tidak dilanjutkan. Alasan: {CANCEL_REASON_LABELS[reason]}"
        recipients = [u for u in [_other_party_user(context), *applicants] if u is not None]
        for user_id in dict.fromkeys(recipients):
            self._notifier.notify(
                user_id, NotificationType.PROJECT_CANCELLED, "Project dibatalkan", body, ReferenceType.PROJECT, project.id
            )
        self._uow.commit()
        return build_detail(self._repository, context)


class StartWork:
    """F-17: hanya freelancer terpilih, setelah pembayaran berhasil."""

    def __init__(self, repository: WorkflowRepository, notifier: Notifier, uow: UnitOfWork, clock: Clock = utc_now):
        self._repository = repository
        self._notifier = notifier
        self._uow = uow
        self._clock = clock
        self._access = ProjectAccess(repository)

    def execute(self, actor: Actor, project_id: str) -> WorkflowDetail:
        context = self._access.load(project_id, actor, lock=True)
        if context.party != Party.FREELANCER:
            raise ForbiddenError("Hanya freelancer terpilih yang dapat memulai pengerjaan")
        if context.project.status == ProjectStatus.SEDANG_DIKERJAKAN:
            return build_detail(self._repository, context)
        if context.project.status != ProjectStatus.SIAP_DIKERJAKAN:
            raise ConflictError(start_blocker(context.project.status))
        payment = self._repository.get_payment(context.agreement.id)
        if payment is None or payment.status != "BERHASIL":
            raise ConflictError(start_blocker(ProjectStatus.MENUNGGU_PEMBAYARAN))

        now = self._clock()
        project = change_status(
            self._repository,
            context.project,
            ProjectStatus.SEDANG_DIKERJAKAN,
            WorkflowAction.START_WORK,
            actor.user_id,
            now,
        )
        context = ProjectContext(project, context.agreement, context.party)
        name = _party_name(self._repository, context)
        self._notifier.notify(
            project.umkm_id,
            NotificationType.WORK_STARTED,
            "Pengerjaan dimulai",
            f"{name} mulai mengerjakan {project.title}",
            ReferenceType.PROJECT,
            project.id,
        )
        self._uow.commit()
        return build_detail(self._repository, context)


class ListMyProjects:
    def __init__(self, repository: WorkflowRepository):
        self._repository = repository

    def execute(
        self, actor: Actor, status: str | None = None, limit: int = 20, offset: int = 0
    ) -> MyProjectsPage:
        if actor.role == UserRole.UMKM:
            party = Party.UMKM
        elif actor.role == UserRole.FREELANCER:
            party = Party.FREELANCER
        else:
            raise ForbiddenError("Hanya UMKM atau freelancer yang memiliki daftar proyek")
        if status is not None:
            try:
                status = ProjectStatus(status).value
            except ValueError:
                raise BadRequestError("Status proyek tidak valid") from None
        if not 1 <= limit <= MAX_PAGE_LIMIT:
            raise BadRequestError(f"Limit harus 1 sampai {MAX_PAGE_LIMIT}")
        if offset < 0:
            raise BadRequestError("Offset tidak boleh negatif")

        rows = self._repository.list_my_projects(actor.user_id, party, status, limit + 1, offset)
        counts = self._repository.count_my_projects_by_status(actor.user_id, party)
        return MyProjectsPage(items=rows[:limit], has_more=len(rows) > limit, status_counts=counts)
