from pydantic import BaseModel, ConfigDict, Field

from app.core.responses import UtcDateTime
from app.modules.reviews.application.use_cases import FreelancerReviewsPage, ReviewInput
from app.modules.reviews.domain.entities import REVIEW_HIGHLIGHT_LABELS, FreelancerReview, ReviewHighlight


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)
    review_text: str | None = Field(None, max_length=2000)
    highlights: list[ReviewHighlight] = Field(default_factory=list, max_length=4, description="Keunggulan Utama")

    def to_input(self) -> ReviewInput:
        return ReviewInput(self.rating, self.review_text, tuple(h.value for h in self.highlights))


class HighlightResponse(BaseModel):
    value: str
    label: str


class ReviewResponse(BaseModel):
    id: str
    project_id: str
    rating: int
    review_text: str | None
    highlights: list[HighlightResponse]
    created_at: UtcDateTime

    @classmethod
    def build(cls, review: FreelancerReview | None) -> "ReviewResponse | None":
        if review is None:
            return None
        return cls(
            id=review.id,
            project_id=review.project_id,
            rating=review.rating,
            review_text=review.review_text,
            highlights=[
                HighlightResponse(value=h, label=REVIEW_HIGHLIGHT_LABELS.get(ReviewHighlight(h), h))
                for h in review.highlights
            ],
            created_at=review.created_at,
        )


class ReviewerResponse(BaseModel):
    user_id: str
    name: str
    business_name: str | None
    profile_image_url: str | None


class PublicReviewResponse(ReviewResponse):
    project_title: str
    reviewer: ReviewerResponse


class FreelancerReviewsResponse(BaseModel):
    average_rating: float | None
    review_count: int
    items: list[PublicReviewResponse]
    limit: int
    offset: int
    has_more: bool

    @classmethod
    def build(cls, page: FreelancerReviewsPage, limit: int, offset: int) -> "FreelancerReviewsResponse":
        items = []
        for row in page.items:
            base = ReviewResponse.build(row.review).model_dump()
            items.append(
                PublicReviewResponse(
                    **base,
                    project_title=row.project_title,
                    reviewer=ReviewerResponse(
                        user_id=row.reviewer.user_id,
                        name=row.reviewer.name,
                        business_name=row.reviewer.business_name,
                        profile_image_url=row.reviewer.profile_image_url,
                    ),
                )
            )
        return cls(
            average_rating=page.summary.average_rating,
            review_count=page.summary.review_count,
            items=items,
            limit=limit,
            offset=offset,
            has_more=page.has_more,
        )
