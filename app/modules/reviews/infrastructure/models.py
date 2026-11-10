from sqlalchemy import CHAR, JSON, CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, CreatedAt, UuidPk
from app.modules.projects.infrastructure import models as _projects_models  # noqa: F401


class FreelancerReviewModel(Base):
    __tablename__ = "freelancer_reviews"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_freelancer_reviews_project"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_freelancer_reviews_rating_range"),
    )

    id: Mapped[UuidPk]
    project_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("projects.id", ondelete="RESTRICT"))
    rating: Mapped[int] = mapped_column(mysql.TINYINT(unsigned=True))
    review_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]
    highlights: Mapped[list | None] = mapped_column(JSON)
