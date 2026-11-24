from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.responses import UtcDateTime
from app.modules.payments.domain.entities import (
    COMMISSION_PERCENT,
    FUND_STATUS_LABELS,
    PAYMENT_METHOD_LABELS,
    PAYMENT_STATUS_LABELS,
    PaymentMethod,
    split_amount,
)
from app.modules.submissions.domain.entities import REVIEW_DECISION_LABELS, version_label
from app.modules.workflow.application.dto import Cancellation, MyProjectsPage, WorkflowDetail
from app.modules.workflow.domain.entities import (
    AGREEMENT_STATUS_LABELS,
    CANCEL_REASON_LABELS,
    WORKFLOW_ACTION_LABELS,
    Agreement,
    AgreementStatus,
    CancelReason,
    MyProjectRow,
    Party,
    PaymentSnapshot,
    ProjectStatus,
    StatusHistoryEntry,
    SubmissionSnapshot,
    UserSummary,
    WorkflowAction,
    WorkflowProject,
    status_label,
)


def _label(labels: dict, value: str | None) -> str | None:
    if value is None:
        return None
    return next((label for key, label in labels.items() if key == value), value)


class SelectFreelancerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: str | None = Field(None, max_length=36, description="Dari daftar pengajuan")
    freelancer_id: str | None = Field(None, max_length=36, description="Pilih langsung dari profil freelancer")
    scope_of_work: str | None = Field(None, max_length=5000, description="Default: deskripsi project")

    @model_validator(mode="after")
    def exactly_one(self):
        if (self.application_id is None) == (self.freelancer_id is None):
            raise ValueError("Isi salah satu: application_id atau freelancer_id")
        return self


class UpdateAgreementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_of_work: str | None = Field(None, min_length=1, max_length=5000)
    agreed_price: int | None = Field(None, ge=1, le=1_000_000_000_000)
    agreed_deadline: date | None = None
    duration_days: int | None = Field(None, ge=1, le=365)


class ApproveAgreementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agreement_version: int | None = Field(
        None, ge=1, description="Versi kesepakatan yang dilihat user; ditolak 409 bila sudah berubah"
    )


class RequestChangesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=1, max_length=2000)


class CancelProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: CancelReason
    note: str | None = Field(None, max_length=500, description="Wajib bila reason = LAINNYA")


class UserSummaryResponse(BaseModel):
    id: str
    name: str
    subtitle: str | None = Field(description="Nama usaha (UMKM) atau jabatan profesional (freelancer)")
    profile_image_url: str | None
    city: str | None
    average_rating: float | None
    review_count: int

    @classmethod
    def build(cls, user: UserSummary | None) -> "UserSummaryResponse | None":
        if user is None:
            return None
        return cls(
            id=user.id,
            name=user.name,
            subtitle=user.subtitle,
            profile_image_url=user.profile_image_url,
            city=user.city,
            average_rating=user.average_rating,
            review_count=user.review_count,
        )


class ProjectSummaryResponse(BaseModel):
    id: str
    title: str
    description: str
    category_id: str
    budget: int
    deadline: date
    status: str
    status_label: str
    published_at: UtcDateTime | None
    started_at: UtcDateTime | None
    completed_at: UtcDateTime | None

    @classmethod
    def build(cls, project: WorkflowProject) -> "ProjectSummaryResponse":
        return cls(
            id=project.id,
            title=project.title,
            description=project.description,
            category_id=project.category_id,
            budget=project.budget,
            deadline=project.deadline,
            status=project.status,
            status_label=status_label(project.status),
            published_at=project.published_at,
            started_at=project.started_at,
            completed_at=project.completed_at,
        )


class AgreementResponse(BaseModel):
    id: str
    project_id: str
    freelancer_id: str
    application_id: str | None
    selection_source: str
    scope_of_work: str
    agreed_price: int
    agreed_deadline: date
    duration_days: int
    commission_percent: int
    platform_fee_amount: int
    freelancer_amount: int
    payment_method: str
    payment_method_label: str
    status: str
    status_label: str
    agreement_version: int
    umkm_approved_at: UtcDateTime | None
    freelancer_approved_at: UtcDateTime | None
    approved_by_me: bool
    waiting_for: list[str] = Field(description="Pihak yang belum menekan Lanjut Project")
    change_request_note: str | None
    change_requested_at: UtcDateTime | None
    created_at: UtcDateTime
    updated_at: UtcDateTime | None

    @classmethod
    def build(cls, agreement: Agreement | None, me: Party) -> "AgreementResponse | None":
        if agreement is None:
            return None
        fee, net = split_amount(agreement.agreed_price)
        waiting = []
        if agreement.status == AgreementStatus.PENDING_APPROVAL:
            waiting = [p.value for p in Party if agreement.approved_at(p) is None]
        return cls(
            id=agreement.id,
            project_id=agreement.project_id,
            freelancer_id=agreement.freelancer_id,
            application_id=agreement.application_id,
            selection_source=agreement.selection_source,
            scope_of_work=agreement.scope_of_work,
            agreed_price=agreement.agreed_price,
            agreed_deadline=agreement.agreed_deadline,
            duration_days=agreement.duration_days,
            commission_percent=COMMISSION_PERCENT,
            platform_fee_amount=fee,
            freelancer_amount=net,
            payment_method=PaymentMethod.QRIS_SIMULATION.value,
            payment_method_label=PAYMENT_METHOD_LABELS[PaymentMethod.QRIS_SIMULATION],
            status=agreement.status,
            status_label=_label(AGREEMENT_STATUS_LABELS, agreement.status),
            agreement_version=agreement.agreement_version,
            umkm_approved_at=agreement.umkm_approved_at,
            freelancer_approved_at=agreement.freelancer_approved_at,
            approved_by_me=agreement.approved_at(me) is not None,
            waiting_for=waiting,
            change_request_note=agreement.change_request_note,
            change_requested_at=agreement.change_requested_at,
            created_at=agreement.created_at,
            updated_at=agreement.updated_at,
        )


class PaymentSummaryResponse(BaseModel):
    id: str
    status: str
    status_label: str
    fund_status: str | None
    fund_status_label: str | None
    gross_amount: int
    platform_fee_amount: int
    freelancer_amount: int
    transaction_number: str | None
    paid_at: UtcDateTime | None
    released_at: UtcDateTime | None
    expires_at: UtcDateTime | None

    @classmethod
    def build(cls, payment: PaymentSnapshot | None) -> "PaymentSummaryResponse | None":
        if payment is None:
            return None
        return cls(
            id=payment.id,
            status=payment.status,
            status_label=_label(PAYMENT_STATUS_LABELS, payment.status),
            fund_status=payment.fund_status,
            fund_status_label=_label(FUND_STATUS_LABELS, payment.fund_status),
            gross_amount=payment.gross_amount,
            platform_fee_amount=payment.platform_fee_amount,
            freelancer_amount=payment.freelancer_amount,
            transaction_number=payment.transaction_number,
            paid_at=payment.paid_at,
            released_at=payment.released_at,
            expires_at=payment.expires_at,
        )


class LatestSubmissionResponse(BaseModel):
    id: str
    version_number: int
    version_label: str
    submitted_at: UtcDateTime
    decision: str | None
    decision_label: str | None

    @classmethod
    def build(cls, submission: SubmissionSnapshot | None) -> "LatestSubmissionResponse | None":
        if submission is None:
            return None
        return cls(
            id=submission.id,
            version_number=submission.version_number,
            version_label=version_label(submission.version_number),
            submitted_at=submission.submitted_at,
            decision=submission.decision,
            decision_label=_label(REVIEW_DECISION_LABELS, submission.decision),
        )


class ActionResponse(BaseModel):
    action: str
    label: str


class HistoryItemResponse(BaseModel):
    id: str
    previous_status: str | None
    previous_status_label: str | None
    new_status: str
    new_status_label: str
    action: str
    action_label: str
    change_source: str
    changed_by_user_id: str | None
    reason_code: str | None
    change_reason: str | None
    changed_at: UtcDateTime

    @classmethod
    def build(cls, entry: StatusHistoryEntry) -> "HistoryItemResponse":
        return cls(
            id=entry.id,
            previous_status=entry.previous_status,
            previous_status_label=status_label(entry.previous_status) if entry.previous_status else None,
            new_status=entry.new_status,
            new_status_label=status_label(entry.new_status),
            action=entry.action,
            action_label=_label(WORKFLOW_ACTION_LABELS, entry.action),
            change_source=entry.change_source,
            changed_by_user_id=entry.changed_by_user_id,
            reason_code=entry.reason_code,
            change_reason=entry.change_reason,
            changed_at=entry.changed_at,
        )


class CancellationResponse(BaseModel):
    reason: str | None
    reason_label: str | None
    note: str | None
    cancelled_by: str | None
    cancelled_at: UtcDateTime
    has_payment: bool = Field(False, description="Selalu false: pembatalan hanya sebelum pembayaran berhasil")

    @classmethod
    def build(cls, cancellation: Cancellation | None) -> "CancellationResponse | None":
        if cancellation is None:
            return None
        return cls(
            reason=cancellation.reason,
            reason_label=_label(CANCEL_REASON_LABELS, cancellation.reason),
            note=cancellation.note,
            cancelled_by=cancellation.cancelled_by.value if cancellation.cancelled_by else None,
            cancelled_at=cancellation.cancelled_at,
        )


def action_items(actions: list[WorkflowAction]) -> list[ActionResponse]:
    return [ActionResponse(action=a.value, label=WORKFLOW_ACTION_LABELS[a]) for a in actions]


class WorkflowDetailResponse(BaseModel):
    project: ProjectSummaryResponse
    my_role: str
    umkm: UserSummaryResponse
    freelancer: UserSummaryResponse | None
    agreement: AgreementResponse | None
    payment: PaymentSummaryResponse | None
    latest_submission: LatestSubmissionResponse | None
    revision_count: int
    has_review: bool
    available_actions: list[ActionResponse]
    history: list[HistoryItemResponse]
    cancellation: CancellationResponse | None

    @classmethod
    def build(cls, detail: WorkflowDetail) -> "WorkflowDetailResponse":
        return cls(
            project=ProjectSummaryResponse.build(detail.project),
            my_role=detail.my_party.value,
            umkm=UserSummaryResponse.build(detail.parties.umkm),
            freelancer=UserSummaryResponse.build(detail.parties.freelancer),
            agreement=AgreementResponse.build(detail.agreement, detail.my_party),
            payment=PaymentSummaryResponse.build(detail.payment),
            latest_submission=LatestSubmissionResponse.build(detail.latest_submission),
            revision_count=detail.revision_count,
            has_review=detail.has_review,
            available_actions=action_items(detail.available_actions),
            history=[HistoryItemResponse.build(h) for h in detail.history],
            cancellation=CancellationResponse.build(detail.cancellation),
        )


class MyProjectAgreementResponse(BaseModel):
    agreed_price: int
    agreed_deadline: date
    duration_days: int
    status: str


class MyProjectItemResponse(BaseModel):
    project: ProjectSummaryResponse
    counterpart: UserSummaryResponse | None = Field(description="Freelancer (untuk UMKM) atau UMKM (untuk freelancer)")
    agreement: MyProjectAgreementResponse | None
    payment: PaymentSummaryResponse | None
    application_count: int = Field(description="Jumlah pengajuan yang masih menunggu keputusan")
    progress_percent: float | None = Field(description="null bila rencana milestone belum ada")

    @classmethod
    def build(cls, row: MyProjectRow) -> "MyProjectItemResponse":
        agreement = None
        if row.agreement is not None:
            agreement = MyProjectAgreementResponse(
                agreed_price=row.agreement.agreed_price,
                agreed_deadline=row.agreement.agreed_deadline,
                duration_days=row.agreement.duration_days,
                status=row.agreement.status,
            )
        return cls(
            project=ProjectSummaryResponse.build(row.project),
            counterpart=UserSummaryResponse.build(row.counterpart),
            agreement=agreement,
            payment=PaymentSummaryResponse.build(row.payment),
            application_count=row.application_count,
            progress_percent=row.progress_percent,
        )


class MyProjectsResponse(BaseModel):
    items: list[MyProjectItemResponse]
    limit: int
    offset: int
    has_more: bool
    status_counts: dict[str, int] = Field(description="Jumlah per status + ALL, untuk tab filter")

    @classmethod
    def build(cls, page: MyProjectsPage, limit: int, offset: int) -> "MyProjectsResponse":
        counts = {status.value: page.status_counts.get(status.value, 0) for status in ProjectStatus}
        counts["ALL"] = sum(counts.values())
        return cls(
            items=[MyProjectItemResponse.build(r) for r in page.items],
            limit=limit,
            offset=offset,
            has_more=page.has_more,
            status_counts=counts,
        )

