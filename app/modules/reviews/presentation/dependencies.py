from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_uow
from app.core.unit_of_work import UnitOfWork
from app.modules.notifications.application.use_cases import Notifier
from app.modules.notifications.presentation.dependencies import get_notifier
from app.modules.reviews.application.use_cases import (
    CreateReview,
    GetProjectReview,
    ListFreelancerReviews,
    ReviewCreator,
)
from app.modules.reviews.domain.repositories import ReviewRepository
from app.modules.reviews.infrastructure.repositories import SqlAlchemyReviewRepository
from app.modules.workflow.domain.repositories import WorkflowRepository
from app.modules.workflow.presentation.providers import get_workflow_repository


def get_review_repository(db: Session = Depends(get_db)) -> ReviewRepository:
    return SqlAlchemyReviewRepository(db)


def get_review_creator(
    reviews: ReviewRepository = Depends(get_review_repository),
    notifier: Notifier = Depends(get_notifier),
) -> ReviewCreator:
    return ReviewCreator(reviews, notifier)


def create_review_use_case(
    workflow: WorkflowRepository = Depends(get_workflow_repository),
    creator: ReviewCreator = Depends(get_review_creator),
    uow: UnitOfWork = Depends(get_uow),
) -> CreateReview:
    return CreateReview(workflow, creator, uow)


def get_project_review_use_case(
    workflow: WorkflowRepository = Depends(get_workflow_repository),
    reviews: ReviewRepository = Depends(get_review_repository),
) -> GetProjectReview:
    return GetProjectReview(workflow, reviews)


def list_freelancer_reviews_use_case(
    workflow: WorkflowRepository = Depends(get_workflow_repository),
    reviews: ReviewRepository = Depends(get_review_repository),
) -> ListFreelancerReviews:
    return ListFreelancerReviews(workflow, reviews)
