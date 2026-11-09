from dataclasses import dataclass
from datetime import datetime


APPLICATION_SUBMITTED = "SUBMITTED"


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
