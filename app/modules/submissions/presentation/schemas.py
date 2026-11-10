from pydantic import BaseModel, ConfigDict, Field

from app.core.config import API_PREFIX
from app.core.responses import UtcDateTime
from app.modules.payments.domain.entities import FUND_STATUS_LABELS
from app.modules.reviews.presentation.schemas import ReviewRequest, ReviewResponse
from app.modules.submissions.application.use_cases import CompletionResult, SubmissionList
from app.modules.submissions.domain.entities import (
    REVIEW_DECISION_LABELS,
    RevisionItem,
    Submission,
    SubmissionFile,
    SubmissionReview,
)
from app.modules.workflow.domain.entities import status_label
from app.modules.workflow.presentation.schemas import UserSummaryResponse


class RevisionItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120, description="Judul poin, mis. Ketebalan Nama Varian Kopi")
    detail: str = Field(min_length=1, max_length=1000, description="Uraian revisi")
    area: str | None = Field(None, max_length=120, description="Area, mis. Label Bagian Depan")


class RevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(None, max_length=5000, description="Catatan umum; wajib bila items kosong")
    focus_areas: list[str] = Field(default_factory=list, max_length=10, description="Kategori Aspek Perbaikan")
    items: list[RevisionItemRequest] = Field(default_factory=list, max_length=20, description="Poin Uraian Revisi")


class ApproveSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review: ReviewRequest | None = Field(None, description="Opsional: Apresiasi & Ulasan")


class SubmissionFileResponse(BaseModel):
    id: str
    original_file_name: str
    mime_type: str
    file_size_bytes: int
    uploaded_at: UtcDateTime
    download_path: str

    @classmethod
    def build(cls, project_id: str, file: SubmissionFile) -> "SubmissionFileResponse":
        return cls(
            id=file.id,
            original_file_name=file.original_file_name,
            mime_type=file.mime_type,
            file_size_bytes=file.file_size_bytes,
            uploaded_at=file.uploaded_at,
            download_path=f"{API_PREFIX}/projects/{project_id}/submissions/{file.submission_id}/files/{file.id}",
        )


class RevisionItemResponse(BaseModel):
    title: str
    detail: str
    area: str | None

    @classmethod
    def build(cls, item: RevisionItem) -> "RevisionItemResponse":
        return cls(title=item.title, detail=item.detail, area=item.area)


class SubmissionReviewResponse(BaseModel):
    decision: str
    decision_label: str
    review_note: str | None
    focus_areas: list[str]
    items: list[RevisionItemResponse]
    reviewed_at: UtcDateTime

    @classmethod
    def build(cls, review: SubmissionReview | None) -> "SubmissionReviewResponse | None":
        if review is None:
            return None
        return cls(
            decision=review.decision,
            decision_label=next((v for k, v in REVIEW_DECISION_LABELS.items() if k == review.decision), review.decision),
            review_note=review.review_note,
            focus_areas=list(review.focus_areas),
            items=[RevisionItemResponse.build(i) for i in review.revision_items],
            reviewed_at=review.reviewed_at,
        )


class SubmissionResponse(BaseModel):
    id: str
    project_id: str
    version_number: int
    version_label: str
    submission_note: str | None
    result_url: str | None
    submitted_at: UtcDateTime
    files: list[SubmissionFileResponse]
    review: SubmissionReviewResponse | None

    @classmethod
    def build(cls, submission: Submission) -> "SubmissionResponse":
        return cls(
            id=submission.id,
            project_id=submission.project_id,
            version_number=submission.version_number,
            version_label=submission.version_label,
            submission_note=submission.submission_note,
            result_url=submission.result_url,
            submitted_at=submission.submitted_at,
            files=[SubmissionFileResponse.build(submission.project_id, f) for f in submission.files],
            review=SubmissionReviewResponse.build(submission.review),
        )


class SubmissionListResponse(BaseModel):
    project_id: str
    project_title: str
    project_status: str
    project_status_label: str
    freelancer: UserSummaryResponse | None
    revision_count: int
    items: list[SubmissionResponse]

    @classmethod
    def build(cls, result: SubmissionList) -> "SubmissionListResponse":
        return cls(
            project_id=result.project.id,
            project_title=result.project.title,
            project_status=result.project.status,
            project_status_label=status_label(result.project.status),
            freelancer=UserSummaryResponse.build(result.parties.freelancer),
            revision_count=result.revision_count,
            items=[SubmissionResponse.build(s) for s in result.items],
        )


class CompletionPaymentResponse(BaseModel):
    id: str
    transaction_number: str | None
    gross_amount: int
    platform_fee_amount: int
    freelancer_amount: int
    fund_status: str | None
    fund_status_label: str | None
    released_at: UtcDateTime | None


class CompletionResponse(BaseModel):
    project_id: str
    project_title: str
    project_status: str
    project_status_label: str
    completed_at: UtcDateTime | None
    freelancer: UserSummaryResponse | None
    submission: SubmissionResponse
    payment: CompletionPaymentResponse
    review: ReviewResponse | None

    @classmethod
    def build(cls, result: CompletionResult) -> "CompletionResponse":
        payment = result.payment
        return cls(
            project_id=result.project.id,
            project_title=result.project.title,
            project_status=result.project.status,
            project_status_label=status_label(result.project.status),
            completed_at=result.project.completed_at,
            freelancer=UserSummaryResponse.build(result.parties.freelancer),
            submission=SubmissionResponse.build(result.submission),
            payment=CompletionPaymentResponse(
                id=payment.id,
                transaction_number=payment.transaction_number,
                gross_amount=payment.gross_amount,
                platform_fee_amount=payment.platform_fee_amount,
                freelancer_amount=payment.freelancer_amount,
                fund_status=payment.fund_status,
                fund_status_label=next(
                    (v for k, v in FUND_STATUS_LABELS.items() if k == payment.fund_status), payment.fund_status
                ),
                released_at=payment.released_at,
            ),
            review=ReviewResponse.build(result.review),
        )
