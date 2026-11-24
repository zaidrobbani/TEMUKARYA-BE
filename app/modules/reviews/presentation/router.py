from fastapi import APIRouter, Depends, Query, status

from app.core.responses import ApiResponse, error_responses, success_response
from app.modules.reviews.application.use_cases import CreateReview, GetProjectReview, ListFreelancerReviews
from app.modules.reviews.presentation.dependencies import (
    create_review_use_case,
    get_project_review_use_case,
    list_freelancer_reviews_use_case,
)
from app.modules.reviews.presentation.schemas import FreelancerReviewsResponse, ReviewRequest, ReviewResponse
from app.modules.workflow.application.dto import Actor
from app.modules.workflow.presentation.providers import get_actor

router = APIRouter(tags=["reviews"])


@router.post(
    "/projects/{project_id}/review",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[ReviewResponse],
    responses=error_responses(400, 401, 403, 404, 409, 422),
    summary="UMKM memberi ulasan freelancer setelah project selesai",
)
def create_review(
    project_id: str,
    body: ReviewRequest,
    actor: Actor = Depends(get_actor),
    use_case: CreateReview = Depends(create_review_use_case),
):
    review = use_case.execute(actor, project_id, body.to_input())
    return success_response("Ulasan terkirim", ReviewResponse.build(review))


@router.get(
    "/projects/{project_id}/review",
    response_model=ApiResponse[ReviewResponse],
    responses=error_responses(401, 404),
)
def get_project_review(
    project_id: str,
    actor: Actor = Depends(get_actor),
    use_case: GetProjectReview = Depends(get_project_review_use_case),
):
    return success_response("Ulasan proyek", ReviewResponse.build(use_case.execute(actor, project_id)))


@router.get(
    "/freelancers/{freelancer_id}/reviews",
    response_model=ApiResponse[FreelancerReviewsResponse],
    responses=error_responses(400, 401, 404, 422),
    summary="Review Klien UMKM di profil freelancer",
)
def list_freelancer_reviews(
    freelancer_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: Actor = Depends(get_actor),
    use_case: ListFreelancerReviews = Depends(list_freelancer_reviews_use_case),
):
    page = use_case.execute(freelancer_id, limit, offset)
    return success_response("Ulasan freelancer", FreelancerReviewsResponse.build(page, limit, offset))
