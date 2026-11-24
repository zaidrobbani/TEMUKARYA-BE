from dataclasses import dataclass
from typing import BinaryIO
from urllib.parse import urlparse
from uuid import uuid4

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.core.unit_of_work import UnitOfWork
from app.modules.notifications.application.use_cases import Notifier
from app.modules.notifications.domain.entities import NotificationType, ReferenceType
from app.modules.payments.application.use_cases import FundReleaser, rupiah
from app.modules.payments.domain.entities import Payment
from app.modules.reviews.application.use_cases import ReviewCreator, ReviewInput
from app.modules.reviews.domain.entities import FreelancerReview
from app.modules.submissions.domain.entities import (
    ALLOWED_FILE_TYPES,
    MAX_FILE_BYTES,
    MAX_FILES,
    RevisionItem,
    ReviewDecision,
    Submission,
    SubmissionFile,
    SubmissionReview,
    file_extension,
    matches_signature,
)
from app.modules.submissions.domain.repositories import SubmissionFileStorage, SubmissionRepository
from app.modules.workflow.application.dto import Actor
from app.modules.workflow.application.services import (
    Clock,
    ProjectAccess,
    ProjectContext,
    change_status,
    utc_now,
)
from app.modules.workflow.domain.entities import (
    Party,
    ProjectParties,
    ProjectStatus,
    WorkflowAction,
    WorkflowProject,
)
from app.modules.workflow.domain.repositories import WorkflowRepository
from app.modules.workflow.domain.rules import WORKING_STATUSES

MAX_NOTE_LENGTH = 5000
MAX_URL_LENGTH = 1000
MAX_FILENAME_LENGTH = 255
MAX_FOCUS_AREAS = 10
MAX_FOCUS_AREA_LENGTH = 60
MAX_REVISION_ITEMS = 20
MAX_ITEM_TITLE = 120
MAX_ITEM_DETAIL = 1000
MAX_REVISION_NOTE = 5000
_HEADER_BYTES = 16


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    size: int
    stream: BinaryIO


@dataclass(frozen=True)
class SubmitResultInput:
    note: str | None = None
    result_url: str | None = None
    files: tuple[UploadedFile, ...] = ()


@dataclass(frozen=True)
class RevisionRequestInput:
    note: str | None = None
    focus_areas: tuple[str, ...] = ()
    items: tuple[RevisionItem, ...] = ()


@dataclass(frozen=True)
class SubmissionList:
    project: WorkflowProject
    parties: ProjectParties
    items: list[Submission]
    revision_count: int


@dataclass(frozen=True)
class CompletionResult:
    project: WorkflowProject
    parties: ProjectParties
    submission: Submission
    payment: Payment
    review: FreelancerReview | None
    already_completed: bool = False


def _revision_count(items: list[Submission]) -> int:
    return sum(1 for s in items if s.review and s.review.decision == ReviewDecision.REVISION_REQUESTED)


class _SubmissionUseCase:
    def __init__(self, workflow: WorkflowRepository, submissions: SubmissionRepository, clock: Clock = utc_now):
        self._workflow = workflow
        self._submissions = submissions
        self._clock = clock
        self._access = ProjectAccess(workflow)

    def _parties(self, context: ProjectContext) -> ProjectParties:
        return self._workflow.get_parties(context.project.umkm_id, context.agreement.freelancer_id)

    def _require_umkm_review(self, context: ProjectContext, submission_id: str) -> Submission:
        if context.party != Party.UMKM:
            raise ForbiddenError("Hanya UMKM pemilik proyek yang dapat meninjau hasil")
        submission = self._submissions.get(context.project.id, submission_id)
        if submission is None:
            raise NotFoundError("Kiriman hasil tidak ditemukan")
        if context.project.status != ProjectStatus.MENUNGGU_REVIEW:
            raise ConflictError("Hasil hanya dapat ditinjau saat proyek Menunggu Review")
        latest = self._submissions.latest(context.project.id)
        if latest is None or latest.id != submission.id or submission.review is not None:
            raise ConflictError("Hanya kiriman terbaru yang belum ditinjau yang dapat diproses")
        return submission


def _validate_files(files: tuple[UploadedFile, ...]) -> list[tuple[UploadedFile, str, str]]:
    if len(files) > MAX_FILES:
        raise BadRequestError(f"Maksimal {MAX_FILES} file per kiriman")
    checked = []
    for upload in files:
        name = (upload.filename or "").strip()
        if not name or len(name) > MAX_FILENAME_LENGTH:
            raise BadRequestError("Nama file tidak valid")
        extension = file_extension(name)
        file_type = ALLOWED_FILE_TYPES.get(extension)
        if file_type is None:
            raise UnsupportedMediaTypeError(
                "Format file tidak didukung. Gunakan AI, PSD, PDF, ZIP, PNG, JPG, MP4, atau DOCX"
            )
        if upload.size <= 0:
            raise BadRequestError(f"File {name} kosong")
        if upload.size > MAX_FILE_BYTES:
            raise PayloadTooLargeError(f"File {name} melebihi 50 MB")
        upload.stream.seek(0)
        header = upload.stream.read(_HEADER_BYTES)
        upload.stream.seek(0)
        if not matches_signature(file_type, header):
            raise BadRequestError(f"Isi file {name} tidak sesuai dengan formatnya")
        checked.append((upload, extension, file_type.mime_type))
    return checked


def _clean_url(value: str | None) -> str | None:
    url = (value or "").strip() or None
    if url is None:
        return None
    parsed = urlparse(url)
    if len(url) > MAX_URL_LENGTH or parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise BadRequestError("Tautan hasil harus URL http/https yang valid")
    return url


class SubmitResult(_SubmissionUseCase):
    """F-18/F-19: kirim hasil atau hasil revisi → Menunggu Review."""

    def __init__(
        self,
        workflow: WorkflowRepository,
        submissions: SubmissionRepository,
        storage: SubmissionFileStorage,
        notifier: Notifier,
        uow: UnitOfWork,
        clock: Clock = utc_now,
    ):
        super().__init__(workflow, submissions, clock)
        self._storage = storage
        self._notifier = notifier
        self._uow = uow

    def execute(self, actor: Actor, project_id: str, data: SubmitResultInput) -> Submission:
        note = (data.note or "").strip() or None
        if note is not None and len(note) > MAX_NOTE_LENGTH:
            raise BadRequestError(f"Catatan maksimal {MAX_NOTE_LENGTH} karakter")
        url = _clean_url(data.result_url)
        files = _validate_files(data.files)
        if not files and url is None:
            raise BadRequestError("Lampirkan minimal satu file atau tautan hasil")

        context = self._access.load(project_id, actor, lock=True)
        if context.party != Party.FREELANCER:
            raise ForbiddenError("Hanya freelancer terpilih yang dapat mengirim hasil")
        status = context.project.status
        if status not in WORKING_STATUSES:
            raise ConflictError(_submit_blocker(status))

        now = self._clock()
        submission_id = str(uuid4())
        saved_keys: list[str] = []
        try:
            stored = []
            for upload, extension, mime_type in files:
                key = self._storage.save(upload.stream, extension)
                saved_keys.append(key)
                stored.append(
                    SubmissionFile(
                        id=str(uuid4()),
                        submission_id=submission_id,
                        original_file_name=upload.filename.strip(),
                        storage_key=key,
                        mime_type=mime_type,
                        file_size_bytes=upload.size,
                        uploaded_at=now,
                    )
                )
            submission = Submission(
                id=submission_id,
                project_id=project_id,
                version_number=self._submissions.next_version(project_id),
                submitted_at=now,
                submission_note=note,
                result_url=url,
                files=tuple(stored),
            )
            self._submissions.add(submission)
            project = change_status(
                self._workflow,
                context.project,
                ProjectStatus.MENUNGGU_REVIEW,
                WorkflowAction.SUBMIT_RESULT,
                actor.user_id,
                now,
            )
            parties = self._parties(context)
            label = "hasil revisi" if status == ProjectStatus.REVISI else "hasil kerja"
            self._notifier.notify(
                project.umkm_id,
                NotificationType.SUBMISSION_RECEIVED,
                f"{parties.freelancer.name if parties.freelancer else 'Freelancer'} mengirim {label}",
                f"{project.title} kini Menunggu Review ({submission.version_label})",
                ReferenceType.PROJECT,
                project_id,
            )
            self._uow.commit()
        except BaseException:
            for key in saved_keys:
                self._storage.delete(key)
            raise
        return submission


def _submit_blocker(status: str) -> str:
    if status == ProjectStatus.MENUNGGU_REVIEW:
        return "Hasil terakhir sedang ditinjau UMKM"
    if status == ProjectStatus.SIAP_DIKERJAKAN:
        return "Tekan Mulai Pengerjaan terlebih dahulu"
    if status == ProjectStatus.SELESAI:
        return "Proyek sudah selesai"
    if status == ProjectStatus.DIBATALKAN:
        return "Proyek sudah dibatalkan"
    return "Hasil hanya dapat dikirim saat proyek Sedang Dikerjakan atau Revisi"


class ListSubmissions(_SubmissionUseCase):
    """U-23: UMKM dan freelancer melihat semua versi kiriman."""

    def execute(self, actor: Actor, project_id: str) -> SubmissionList:
        context = self._access.load(project_id, actor)
        if context.agreement is None:
            raise NotFoundError("Proyek ini belum memiliki kiriman hasil")
        items = self._submissions.list_for_project(project_id)
        return SubmissionList(context.project, self._parties(context), items, _revision_count(items))


class GetSubmission(_SubmissionUseCase):
    def execute(self, actor: Actor, project_id: str, submission_id: str) -> Submission:
        self._access.load(project_id, actor)
        submission = self._submissions.get(project_id, submission_id)
        if submission is None:
            raise NotFoundError("Kiriman hasil tidak ditemukan")
        return submission


class OpenSubmissionFile(_SubmissionUseCase):
    def __init__(
        self,
        workflow: WorkflowRepository,
        submissions: SubmissionRepository,
        storage: SubmissionFileStorage,
        clock: Clock = utc_now,
    ):
        super().__init__(workflow, submissions, clock)
        self._storage = storage

    def execute(
        self, actor: Actor, project_id: str, submission_id: str, file_id: str
    ) -> tuple[SubmissionFile, BinaryIO]:
        self._access.load(project_id, actor)
        submission = self._submissions.get(project_id, submission_id)
        file = next((f for f in submission.files if f.id == file_id), None) if submission else None
        if file is None:
            raise NotFoundError("File tidak ditemukan")
        return file, self._storage.open(file.storage_key)


def _clean_revision(data: RevisionRequestInput) -> tuple[str, tuple[str, ...], tuple[RevisionItem, ...]]:
    note = (data.note or "").strip() or None
    if note is not None and len(note) > MAX_REVISION_NOTE:
        raise BadRequestError(f"Catatan revisi maksimal {MAX_REVISION_NOTE} karakter")
    if len(data.focus_areas) > MAX_FOCUS_AREAS:
        raise BadRequestError(f"Maksimal {MAX_FOCUS_AREAS} aspek perbaikan")
    areas: list[str] = []
    for area in data.focus_areas:
        area = (area or "").strip()
        if not area or len(area) > MAX_FOCUS_AREA_LENGTH:
            raise BadRequestError(f"Aspek perbaikan wajib diisi, maksimal {MAX_FOCUS_AREA_LENGTH} karakter")
        if area not in areas:
            areas.append(area)
    if len(data.items) > MAX_REVISION_ITEMS:
        raise BadRequestError(f"Maksimal {MAX_REVISION_ITEMS} poin revisi")
    items: list[RevisionItem] = []
    for item in data.items:
        title, detail = (item.title or "").strip(), (item.detail or "").strip()
        area = (item.area or "").strip() or None
        if not title or len(title) > MAX_ITEM_TITLE:
            raise BadRequestError(f"Judul poin revisi wajib diisi, maksimal {MAX_ITEM_TITLE} karakter")
        if not detail or len(detail) > MAX_ITEM_DETAIL:
            raise BadRequestError(f"Uraian poin revisi wajib diisi, maksimal {MAX_ITEM_DETAIL} karakter")
        if area is not None and len(area) > MAX_ITEM_TITLE:
            raise BadRequestError(f"Area poin revisi maksimal {MAX_ITEM_TITLE} karakter")
        items.append(RevisionItem(title, detail, area))
    if note is None and not items:
        raise BadRequestError("Catatan revisi wajib diisi")
    # review_note wajib terisi untuk revisi (constraint DB); susun dari poin bila catatan kosong.
    review_note = note or "\n".join(f"{i}. {it.title}: {it.detail}" for i, it in enumerate(items, start=1))
    return review_note[:MAX_REVISION_NOTE], tuple(areas), tuple(items)


class RequestRevision(_SubmissionUseCase):
    """U-24: UMKM meminta revisi kiriman terbaru → Revisi."""

    def __init__(
        self,
        workflow: WorkflowRepository,
        submissions: SubmissionRepository,
        notifier: Notifier,
        uow: UnitOfWork,
        clock: Clock = utc_now,
    ):
        super().__init__(workflow, submissions, clock)
        self._notifier = notifier
        self._uow = uow

    def execute(
        self, actor: Actor, project_id: str, submission_id: str, data: RevisionRequestInput
    ) -> Submission:
        note, areas, items = _clean_revision(data)
        context = self._access.load(project_id, actor, lock=True)
        submission = self._require_umkm_review(context, submission_id)
        now = self._clock()
        review = SubmissionReview(
            id=str(uuid4()),
            submission_id=submission.id,
            reviewer_user_id=actor.user_id,
            decision=ReviewDecision.REVISION_REQUESTED.value,
            reviewed_at=now,
            review_note=note,
            focus_areas=areas,
            revision_items=items,
        )
        self._submissions.add_review(review)
        project = change_status(
            self._workflow,
            context.project,
            ProjectStatus.REVISI,
            WorkflowAction.REQUEST_REVISION,
            actor.user_id,
            now,
            reason=note,
        )
        revision_number = _revision_count(self._submissions.list_for_project(project_id))
        self._notifier.notify(
            context.agreement.freelancer_id,
            NotificationType.REVISION_REQUESTED,
            "Permintaan revisi diterima",
            f"Revisi ke-{revision_number} untuk {project.title} ({submission.version_label})",
            ReferenceType.PROJECT,
            project_id,
        )
        self._uow.commit()
        return self._submissions.get(project_id, submission.id)


class ApproveSubmission(_SubmissionUseCase):
    """U-25: setujui hasil → Selesai + dana RELEASED dalam satu transaksi. Request ulang tidak melepas dana lagi."""

    def __init__(
        self,
        workflow: WorkflowRepository,
        submissions: SubmissionRepository,
        releaser: FundReleaser,
        reviews: ReviewCreator,
        notifier: Notifier,
        uow: UnitOfWork,
        clock: Clock = utc_now,
    ):
        super().__init__(workflow, submissions, clock)
        self._releaser = releaser
        self._reviews = reviews
        self._notifier = notifier
        self._uow = uow

    def execute(
        self, actor: Actor, project_id: str, submission_id: str, review: ReviewInput | None = None
    ) -> CompletionResult:
        if review is not None:
            review = self._reviews.validate(review)
        context = self._access.load(project_id, actor, lock=True)

        if context.party == Party.UMKM and context.project.status == ProjectStatus.SELESAI:
            done = self._submissions.get(project_id, submission_id)
            if done is not None and done.review and done.review.decision == ReviewDecision.APPROVED:
                payment = self._releaser.current(context.agreement)
                return CompletionResult(
                    context.project, self._parties(context), done, payment, None, already_completed=True
                )

        submission = self._require_umkm_review(context, submission_id)
        now = self._clock()
        self._submissions.add_review(
            SubmissionReview(
                id=str(uuid4()),
                submission_id=submission.id,
                reviewer_user_id=actor.user_id,
                decision=ReviewDecision.APPROVED.value,
                reviewed_at=now,
            )
        )
        project = change_status(
            self._workflow,
            context.project,
            ProjectStatus.SELESAI,
            WorkflowAction.APPROVE_RESULT,
            actor.user_id,
            now,
        )
        payment = self._releaser.release(context.agreement, project.title, now)
        created_review = None
        if review is not None:
            created_review = self._reviews.create(project, context.agreement.freelancer_id, review, now)

        freelancer_id = context.agreement.freelancer_id
        self._notifier.notify(
            freelancer_id,
            NotificationType.SUBMISSION_APPROVED,
            "Hasil disetujui, proyek selesai",
            f"UMKM menyetujui {submission.version_label} untuk {project.title}",
            ReferenceType.PROJECT,
            project_id,
        )
        self._notifier.notify(
            freelancer_id,
            NotificationType.FUNDS_RELEASED,
            "Dana diteruskan ke dompetmu",
            f"{rupiah(payment.freelancer_amount)} dari {project.title} kini masuk saldo tersedia",
            ReferenceType.PROJECT,
            project_id,
        )
        self._uow.commit()
        return CompletionResult(
            project,
            self._parties(context),
            self._submissions.get(project_id, submission.id),
            payment,
            created_review,
        )
