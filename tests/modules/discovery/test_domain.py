
from dataclasses import FrozenInstanceError, asdict
from datetime import date, datetime

import pytest

from app.modules.discovery.domain.entities import (
    FreelancerDetail,
    FreelancerPortfolio,
    FreelancerReview,
    FreelancerSearchFilters,
    FreelancerSkill,
    FreelancerSummary,
    FreelancerWorkExperience,
)

from app.modules.discovery.domain.repositories import (
    DiscoveryRepository,
)


# ============================================================
# TEST DATA FACTORIES
# ============================================================

FREELANCER_ID = (
    "11111111-1111-4111-8111-111111111111"
)


def make_summary():
    return FreelancerSummary(
        user_id=FREELANCER_ID,
        name="Andi",
        professional_title="Web Developer",
        city="Malang",
        availability_status="AVAILABLE",
        service_price_min=500000,
        service_price_max=2000000,
        skills=(
            FreelancerSkill(
                id="python",
                name="Python",
            ),
            FreelancerSkill(
                id="fastapi",
                name="FastAPI",
            ),
        ),
        experience_count=3,
        average_rating=4.5,
        review_count=2,
    )


# ============================================================
# FREELANCER SUMMARY TESTS
# ============================================================

def test_freelancer_summary_fields():
    freelancer = make_summary()

    assert freelancer.user_id == FREELANCER_ID
    assert freelancer.name == "Andi"
    assert freelancer.professional_title == "Web Developer"
    assert freelancer.city == "Malang"

    assert freelancer.service_price_min == 500000
    assert freelancer.service_price_max == 2000000

    assert freelancer.experience_count == 3
    assert freelancer.average_rating == 4.5
    assert freelancer.review_count == 2


def test_freelancer_skills_are_available():
    freelancer = make_summary()

    assert len(freelancer.skills) == 2

    skill_names = [
        skill.name
        for skill in freelancer.skills
    ]

    assert "Python" in skill_names
    assert "FastAPI" in skill_names


def test_new_freelancer_has_no_rating():
    freelancer = FreelancerSummary(
        user_id=FREELANCER_ID,
        name="Andi",
        professional_title="Web Developer",
        city="Malang",
        availability_status="AVAILABLE",
    )

    assert freelancer.average_rating is None
    assert freelancer.review_count == 0
    assert freelancer.experience_count == 0
    assert freelancer.skills == ()


def test_freelancer_summary_is_immutable():
    freelancer = make_summary()

    with pytest.raises(FrozenInstanceError):
        freelancer.name = "Nama Baru"


def test_summary_does_not_expose_credentials():
    freelancer = make_summary()

    data = asdict(freelancer)

    assert "password_hash" not in data
    assert "password" not in data
    assert "email" not in data


# ============================================================
# FREELANCER DETAIL TESTS
# ============================================================

def test_freelancer_detail():
    detail = FreelancerDetail(
        user_id=FREELANCER_ID,
        name="Andi",
        professional_title="Web Developer",
        city="Malang",
        availability_status="AVAILABLE",
        bio="Saya seorang Backend Developer.",
        experiences=(
            FreelancerWorkExperience(
                id="experience-1",
                job_title="Backend Developer",
                organization_name="Tech Company",
                description="Mengembangkan REST API.",
                start_date=date(2024, 1, 1),
                end_date=date(2025, 1, 1),
            ),
        ),
        portfolios=(
            FreelancerPortfolio(
                id="portfolio-1",
                title="Website UMKM",
                description="Website toko online.",
                project_url="https://example.com",
            ),
        ),
        reviews=(
            FreelancerReview(
                id="review-1",
                project_id="project-1",
                rating=5,
                review_text="Hasil pekerjaan sangat bagus.",
                created_at=datetime(2026, 11, 2),
            ),
        ),
    )

    assert detail.name == "Andi"
    assert detail.bio == (
        "Saya seorang Backend Developer."
    )

    assert len(detail.experiences) == 1
    assert len(detail.portfolios) == 1
    assert len(detail.reviews) == 1

    assert detail.reviews[0].rating == 5


def test_freelancer_detail_defaults():
    detail = FreelancerDetail(
        user_id=FREELANCER_ID,
        name="Andi",
        professional_title="Web Developer",
        city="Malang",
        availability_status="AVAILABLE",
    )

    assert detail.bio is None
    assert detail.experiences == ()
    assert detail.portfolios == ()
    assert detail.reviews == ()


def test_freelancer_experience_optional_end_date():
    experience = FreelancerWorkExperience(
        id="experience-1",
        job_title="Software Engineer",
        organization_name="Company",
        description="Membangun aplikasi.",
        start_date=date(2025, 1, 1),
    )

    assert experience.end_date is None


def test_freelancer_portfolio_optional_url():
    portfolio = FreelancerPortfolio(
        id="portfolio-1",
        title="Desain Logo",
        description="Desain identitas brand.",
    )

    assert portfolio.project_url is None


def test_freelancer_review_optional_text():
    review = FreelancerReview(
        id="review-1",
        project_id="project-1",
        rating=5,
    )

    assert review.review_text is None
    assert review.created_at is None


# ============================================================
# SEARCH FILTER TESTS
# ============================================================

def test_default_search_filters():
    filters = FreelancerSearchFilters()

    assert filters.search is None
    assert filters.skill_ids == ()
    assert filters.city is None
    assert filters.availability_status == "AVAILABLE"
    assert filters.min_price is None
    assert filters.max_price is None
    assert filters.min_experience_count is None
    assert filters.min_rating is None


def test_search_filters_can_be_configured():
    filters = FreelancerSearchFilters(
        search="backend",
        skill_ids=("python", "fastapi"),
        city="Malang",
        availability_status="AVAILABLE",
        min_price=500000,
        max_price=2000000,
        min_experience_count=2,
        min_rating=4.0,
    )

    assert filters.search == "backend"
    assert filters.skill_ids == ("python", "fastapi")
    assert filters.city == "Malang"
    assert filters.min_price == 500000
    assert filters.max_price == 2000000
    assert filters.min_experience_count == 2
    assert filters.min_rating == 4.0


# ============================================================
# REPOSITORY CONTRACT TESTS
# ============================================================

@pytest.mark.parametrize(
    "method_name",
    [
        "search_freelancers",
        "get_freelancer_detail",
    ],
)
def test_discovery_repository_contract_exists(
    method_name,
):
    assert callable(
        getattr(
            DiscoveryRepository,
            method_name,
            None,
        )
    )