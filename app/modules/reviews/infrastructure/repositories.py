from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import from_db_utc, to_db_utc
from app.modules.reviews.domain.entities import (
    FreelancerReview,
    PublicReview,
    RatingSummary,
    ReviewerSummary,
)
from app.modules.reviews.domain.repositories import ReviewRepository
from app.modules.reviews.infrastructure.models import FreelancerReviewModel


def _review(model: FreelancerReviewModel) -> FreelancerReview:
    return FreelancerReview(
        id=model.id,
        project_id=model.project_id,
        rating=int(model.rating),
        created_at=from_db_utc(model.created_at),
        review_text=model.review_text,
        highlights=tuple(model.highlights or ()),
    )


class SqlAlchemyReviewRepository(ReviewRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_by_project(self, project_id: str) -> FreelancerReview | None:
        model = self._session.scalar(
            select(FreelancerReviewModel).where(FreelancerReviewModel.project_id == project_id)
        )
        return _review(model) if model else None

    def add(self, review: FreelancerReview) -> None:
        self._session.add(
            FreelancerReviewModel(
                id=review.id,
                project_id=review.project_id,
                rating=review.rating,
                review_text=review.review_text,
                highlights=list(review.highlights) or None,
                created_at=to_db_utc(review.created_at),
            )
        )
        self._session.flush()

    def list_for_freelancer(self, freelancer_id: str, limit: int, offset: int) -> list[PublicReview]:
        rows = self._session.execute(
            text(
                "SELECT fr.id, pr.title, u.id AS reviewer_id, u.name, u.profile_image_url, up.business_name "
                "FROM freelancer_reviews fr "
                "JOIN project_agreements pa ON pa.project_id = fr.project_id "
                "JOIN projects pr ON pr.id = fr.project_id "
                "JOIN users u ON u.id = pr.umkm_id "
                "LEFT JOIN umkm_profiles up ON up.user_id = u.id "
                "WHERE pa.freelancer_id = :fid "
                "ORDER BY fr.created_at DESC, fr.id LIMIT :limit OFFSET :offset"
            ),
            {"fid": freelancer_id, "limit": limit, "offset": offset},
        ).mappings().all()
        if not rows:
            return []
        models = {
            m.id: m
            for m in self._session.scalars(
                select(FreelancerReviewModel).where(FreelancerReviewModel.id.in_([r["id"] for r in rows]))
            )
        }
        return [
            PublicReview(
                review=_review(models[r["id"]]),
                project_title=r["title"],
                reviewer=ReviewerSummary(
                    user_id=r["reviewer_id"],
                    name=r["name"],
                    business_name=r["business_name"],
                    profile_image_url=r["profile_image_url"],
                ),
            )
            for r in rows
        ]

    def summary_for_freelancer(self, freelancer_id: str) -> RatingSummary:
        row = self._session.execute(
            text(
                "SELECT AVG(fr.rating) AS average_rating, COUNT(*) AS review_count "
                "FROM freelancer_reviews fr JOIN project_agreements pa ON pa.project_id = fr.project_id "
                "WHERE pa.freelancer_id = :fid"
            ),
            {"fid": freelancer_id},
        ).mappings().one()
        average = row["average_rating"]
        return RatingSummary(
            average_rating=round(float(average), 2) if average is not None else None,
            review_count=int(row["review_count"]),
        )
