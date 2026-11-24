from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ApplicationStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    NOT_SELECTED = "NOT_SELECTED"
    CANCELLED = "CANCELLED"


APPLICATION_STATUS_LABELS = {
    ApplicationStatus.SUBMITTED: "Menunggu",
    ApplicationStatus.ACCEPTED: "Disetujui",
    ApplicationStatus.NOT_SELECTED: "Tidak dipilih",
    ApplicationStatus.CANCELLED: "Dibatalkan",
}

APPLICATION_SUBMITTED = ApplicationStatus.SUBMITTED.value


@dataclass(frozen=True)
class ProjectApplication:
    """
    Merepresentasikan satu lamaran Freelancer
    terhadap satu proyek UMKM.
    """

    id: str
    project_id: str
    freelancer_id: str
    proposed_price: int
    estimated_duration_days: int
    proposal_message: str

    status: str = APPLICATION_SUBMITTED

    submitted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
