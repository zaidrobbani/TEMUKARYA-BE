from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

WIB = timedelta(hours=7)


def wib_date(moment: datetime) -> date:
    """Tanggal kalender Indonesia (WIB) dari waktu UTC."""
    return (moment + WIB).date()


class ProjectStatus(StrEnum):
    TERBUKA = "TERBUKA"
    MENUNGGU_KESEPAKATAN = "MENUNGGU_KESEPAKATAN"
    MENUNGGU_PEMBAYARAN = "MENUNGGU_PEMBAYARAN"
    SIAP_DIKERJAKAN = "SIAP_DIKERJAKAN"
    SEDANG_DIKERJAKAN = "SEDANG_DIKERJAKAN"
    MENUNGGU_REVIEW = "MENUNGGU_REVIEW"
    REVISI = "REVISI"
    SELESAI = "SELESAI"
    DIBATALKAN = "DIBATALKAN"


PROJECT_STATUS_LABELS: dict[ProjectStatus, str] = {
    ProjectStatus.TERBUKA: "Terbuka",
    ProjectStatus.MENUNGGU_KESEPAKATAN: "Menunggu Kesepakatan",
    ProjectStatus.MENUNGGU_PEMBAYARAN: "Menunggu Pembayaran",
    ProjectStatus.SIAP_DIKERJAKAN: "Siap Dikerjakan",
    ProjectStatus.SEDANG_DIKERJAKAN: "Sedang Dikerjakan",
    ProjectStatus.MENUNGGU_REVIEW: "Menunggu Review",
    ProjectStatus.REVISI: "Revisi",
    ProjectStatus.SELESAI: "Selesai",
    ProjectStatus.DIBATALKAN: "Dibatalkan",
}


def status_label(status: str) -> str:
    try:
        return PROJECT_STATUS_LABELS[ProjectStatus(status)]
    except ValueError:
        return status


class AgreementStatus(StrEnum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"


AGREEMENT_STATUS_LABELS = {
    AgreementStatus.PENDING_APPROVAL: "Menunggu persetujuan",
    AgreementStatus.APPROVED: "Disepakati",
    AgreementStatus.CANCELLED: "Dibatalkan",
}


class SelectionSource(StrEnum):
    APPLICATION = "APPLICATION"
    DIRECT = "DIRECT"


class CancelReason(StrEnum):
    HARGA_TIDAK_SESUAI = "HARGA_TIDAK_SESUAI"
    JADWAL_TIDAK_COCOK = "JADWAL_TIDAK_COCOK"
    KEBUTUHAN_BERUBAH = "KEBUTUHAN_BERUBAH"
    LAINNYA = "LAINNYA"


CANCEL_REASON_LABELS = {
    CancelReason.HARGA_TIDAK_SESUAI: "Harga belum sesuai",
    CancelReason.JADWAL_TIDAK_COCOK: "Jadwal pengerjaan tidak cocok",
    CancelReason.KEBUTUHAN_BERUBAH: "Kebutuhan project berubah",
    CancelReason.LAINNYA: "Alasan lainnya",
}


class WorkflowAction(StrEnum):
    SELECT_FREELANCER = "SELECT_FREELANCER"
    UPDATE_AGREEMENT = "UPDATE_AGREEMENT"
    EDIT_MILESTONE_PLAN = "EDIT_MILESTONE_PLAN"
    APPROVE_AGREEMENT = "APPROVE_AGREEMENT"
    REQUEST_AGREEMENT_CHANGES = "REQUEST_AGREEMENT_CHANGES"
    PAY = "PAY"
    PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
    START_WORK = "START_WORK"
    COMPLETE_MILESTONE = "COMPLETE_MILESTONE"
    SUBMIT_RESULT = "SUBMIT_RESULT"
    REQUEST_REVISION = "REQUEST_REVISION"
    APPROVE_RESULT = "APPROVE_RESULT"
    GIVE_REVIEW = "GIVE_REVIEW"
    CANCEL_PROJECT = "CANCEL_PROJECT"


WORKFLOW_ACTION_LABELS = {
    WorkflowAction.SELECT_FREELANCER: "Pilih freelancer",
    WorkflowAction.UPDATE_AGREEMENT: "Ubah kesepakatan",
    WorkflowAction.EDIT_MILESTONE_PLAN: "Susun rencana pengerjaan",
    WorkflowAction.APPROVE_AGREEMENT: "Lanjut project",
    WorkflowAction.REQUEST_AGREEMENT_CHANGES: "Minta ubah rencana",
    WorkflowAction.PAY: "Bayar",
    WorkflowAction.PAYMENT_SUCCEEDED: "Pembayaran berhasil",
    WorkflowAction.START_WORK: "Mulai pengerjaan",
    WorkflowAction.COMPLETE_MILESTONE: "Tandai milestone selesai",
    WorkflowAction.SUBMIT_RESULT: "Kirim hasil",
    WorkflowAction.REQUEST_REVISION: "Minta revisi",
    WorkflowAction.APPROVE_RESULT: "Setujui hasil",
    WorkflowAction.GIVE_REVIEW: "Beri ulasan",
    WorkflowAction.CANCEL_PROJECT: "Batalkan project",
}


class ChangeSource(StrEnum):
    USER = "USER"
    SYSTEM = "SYSTEM"


class Party(StrEnum):
    UMKM = "UMKM"
    FREELANCER = "FREELANCER"


@dataclass(frozen=True)
class WorkflowProject:
    id: str
    umkm_id: str
    category_id: str
    title: str
    description: str
    budget: int
    deadline: date
    status: str
    published_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class Agreement:
    id: str
    project_id: str
    freelancer_id: str
    application_id: str | None
    selection_source: str
    scope_of_work: str
    agreed_price: int
    agreed_deadline: date
    status: str
    agreement_version: int
    created_at: datetime
    umkm_approved_at: datetime | None = None
    freelancer_approved_at: datetime | None = None
    change_request_note: str | None = None
    change_requested_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def duration_days(self) -> int:
        return (self.agreed_deadline - wib_date(self.created_at)).days

    def approved_at(self, party: Party) -> datetime | None:
        return self.umkm_approved_at if party == Party.UMKM else self.freelancer_approved_at

    @property
    def both_approved(self) -> bool:
        return self.umkm_approved_at is not None and self.freelancer_approved_at is not None


@dataclass(frozen=True)
class StatusHistoryEntry:
    id: str
    project_id: str
    previous_status: str | None
    new_status: str
    action: str
    change_source: str
    changed_at: datetime
    changed_by_user_id: str | None = None
    change_reason: str | None = None
    reason_code: str | None = None


@dataclass(frozen=True)
class ApplicationSnapshot:
    id: str
    project_id: str
    freelancer_id: str
    proposed_price: int
    estimated_duration_days: int
    status: str


@dataclass(frozen=True)
class UserSummary:
    id: str
    name: str
    subtitle: str | None = None
    profile_image_url: str | None = None
    city: str | None = None
    average_rating: float | None = None
    review_count: int = 0


@dataclass(frozen=True)
class ProjectParties:
    umkm: UserSummary
    freelancer: UserSummary | None


@dataclass(frozen=True)
class SubmissionSnapshot:
    id: str
    version_number: int
    submitted_at: datetime
    decision: str | None


@dataclass(frozen=True)
class PaymentSnapshot:
    id: str
    status: str
    fund_status: str | None
    gross_amount: int
    platform_fee_amount: int
    freelancer_amount: int
    transaction_number: str | None
    paid_at: datetime | None
    released_at: datetime | None
    expires_at: datetime | None


@dataclass(frozen=True)
class MyProjectRow:
    project: WorkflowProject
    agreement: Agreement | None
    counterpart: UserSummary | None
    payment: PaymentSnapshot | None
    application_count: int
    progress_percent: float | None
