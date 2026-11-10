from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.unit_of_work import UnitOfWork
from app.modules.notifications.application.use_cases import Notifier
from app.modules.notifications.domain.entities import NotificationType, ReferenceType
from app.modules.reviews.domain.entities import (
    FreelancerReview,
    PublicReview,
    RatingSummary,
    ReviewHighlight,
)
from app.modules.reviews.domain.repositories import ReviewRepository
from app.modules.workflow.application.dto import Actor
from app.modules.workflow.application.services import Clock, ProjectAccess, utc_now
from app.modules.workflow.domain.entities import Party, ProjectStatus, WorkflowProject
from app.modules.workflow.domain.repositories import WorkflowRepository

MAX_REVIEW_TEXT = 2000
MAX_PAGE_LIMIT = 100


@dataclass(frozen=True)
class ReviewInput:
    rating: int
    review_text: str | None = None
    highlights: tuple[str, ...] = ()


@dataclass(frozen=True)
class FreelancerReviewsPage:
    summary: RatingSummary
    items: list[PublicReview]
    has_more: bool


class ReviewCreator:
    """Membuat ulasan; dipakai endpoint ulasan dan alur Setujui & Selesai. Tidak commit."""

    def __init__(self, reviews: ReviewRepository, notifier: Notifier):
        self._reviews = reviews
        self._notifier = notifier

    def validate(self, data: ReviewInput) -> ReviewInput:
        if type(data.rating) is not int or not 1 <= data.rating <= 5:
            raise BadRequestError("Rating harus angka bulat 1 sampai 5")
        text = (data.review_text or "").strip() or None
        if text is not None and len(text) > MAX_REVIEW_TEXT:
            raise BadRequestError(f"Ulasan maksimal {MAX_REVIEW_TEXT} karakter")
        highlights: list[str] = []
        for value in data.highlights:
            try:
                highlight = ReviewHighlight(value).value
            except ValueError:
                raise BadRequestError("Keunggulan ulasan tidak valid") from None
            if highlight not in highlights:
                highlights.append(highlight)
        return ReviewInput(data.rating, text, tuple(highlights))

    def create(
        self, project: WorkflowProject, freelancer_id: str, data: ReviewInput, now: datetime
    ) -> FreelancerReview:
        data = self.validate(data)
        if project.status != ProjectStatus.SELESAI:
            raise ConflictError("Ulasan hanya dapat diberikan setelah proyek selesai")
        if self._reviews.get_by_project(project.id) is not None:
            raise ConflictError("Proyek ini sudah diberi ulasan")
        review = FreelancerReview(
            id=str(uuid4()),
            project_id=project.id,
            rating=data.rating,
            created_at=now,
            review_text=data.review_text,
            highlights=data.highlights,
        )
        self._reviews.add(review)
        self._notifier.notify(
            freelancer_id,
            NotificationType.REVIEW_RECEIVED,
            f"Ulasan baru ({data.rating}/5)",
            f"UMKM memberi ulasan untuk {project.title}",
            ReferenceType.PROJECT,
            project.id,
        )
        return review


class CreateReview:
    def __init__(
        self,
        workflow: WorkflowRepository,
        creator: ReviewCreator,
        uow: UnitOfWork,
        clock: Clock = utc_now,
    ):
        self._access = ProjectAccess(workflow)
        self._creator = creator
        self._uow = uow
        self._clock = clock

    def execute(self, actor: Actor, project_id: str, data: ReviewInput) -> FreelancerReview:
        self._creator.validate(data)
        context = self._access.load(project_id, actor, lock=True)
        if context.party != Party.UMKM:
            raise ForbiddenError("Hanya UMKM pemilik proyek yang dapat memberi ulasan")
        review = self._creator.create(context.project, context.agreement.freelancer_id, data, self._clock())
        self._uow.commit()
        return review


class GetProjectReview:
    def __init__(self, workflow: WorkflowRepository, reviews: ReviewRepository):
        self._access = ProjectAccess(workflow)
        self._reviews = reviews

    def execute(self, actor: Actor, project_id: str) -> FreelancerReview:
        self._access.load(project_id, actor)
        review = self._reviews.get_by_project(project_id)
        if review is None:
            raise NotFoundError("Proyek ini belum diberi ulasan")
        return review


class ListFreelancerReviews:
    def __init__(self, workflow: WorkflowRepository, reviews: ReviewRepository):
        self._workflow = workflow
        self._reviews = reviews

    def execute(self, freelancer_id: str, limit: int = 20, offset: int = 0) -> FreelancerReviewsPage:
        if not 1 <= limit <= MAX_PAGE_LIMIT:
            raise BadRequestError(f"Limit harus 1 sampai {MAX_PAGE_LIMIT}")
        if offset < 0:
            raise BadRequestError("Offset tidak boleh negatif")
        if not self._workflow.is_freelancer(freelancer_id):
            raise NotFoundError("Freelancer tidak ditemukan")
        rows = self._reviews.list_for_freelancer(freelancer_id, limit + 1, offset)
        return FreelancerReviewsPage(
            summary=self._reviews.summary_for_freelancer(freelancer_id),
            items=rows[:limit],
            has_more=len(rows) > limit,
        )
