from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReviewHighlight(StrEnum):
    RESPONSIF_KOMUNIKATIF = "RESPONSIF_KOMUNIKATIF"
    HASIL_BERKUALITAS = "HASIL_BERKUALITAS"
    TEPAT_WAKTU = "TEPAT_WAKTU"
    PAHAM_KEBUTUHAN = "PAHAM_KEBUTUHAN"


REVIEW_HIGHLIGHT_LABELS = {
    ReviewHighlight.RESPONSIF_KOMUNIKATIF: "Responsif & Komunikatif",
    ReviewHighlight.HASIL_BERKUALITAS: "Hasil Sesuai & Berkualitas",
    ReviewHighlight.TEPAT_WAKTU: "Tepat Waktu",
    ReviewHighlight.PAHAM_KEBUTUHAN: "Paham Kebutuhan UMKM",
}


@dataclass(frozen=True)
class FreelancerReview:
    id: str
    project_id: str
    rating: int
    created_at: datetime
    review_text: str | None = None
    highlights: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewerSummary:
    user_id: str
    name: str
    business_name: str | None
    profile_image_url: str | None


@dataclass(frozen=True)
class PublicReview:
    review: FreelancerReview
    project_title: str
    reviewer: ReviewerSummary


@dataclass(frozen=True)
class RatingSummary:
    average_rating: float | None
    review_count: int
