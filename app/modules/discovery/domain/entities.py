from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class FreelancerSkill:
    id: str
    name: str


@dataclass(frozen=True)
class FreelancerWorkExperience:
    id: str
    job_title: str
    organization_name: str
    description: str
    start_date: date
    end_date: date | None = None


@dataclass(frozen=True)
class FreelancerPortfolio:
    id: str
    title: str
    description: str
    project_url: str | None = None
    cover_image_url: str | None = None


@dataclass(frozen=True)
class FreelancerReview:
    id: str
    project_id: str
    rating: int
    review_text: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class FreelancerSummary:
    user_id: str
    name: str
    professional_title: str
    city: str
    availability_status: str

    service_price_min: int | None = None
    service_price_max: int | None = None

    skills: tuple[FreelancerSkill, ...] = ()

    experience_count: int = 0

    average_rating: float | None = None
    review_count: int = 0

    profile_image_url: str | None = None


@dataclass(frozen=True)
class FreelancerDetail(FreelancerSummary):
    bio: str | None = None

    experiences: tuple[
        FreelancerWorkExperience, ...
    ] = ()

    portfolios: tuple[
        FreelancerPortfolio, ...
    ] = ()

    reviews: tuple[
        FreelancerReview, ...
    ] = ()


@dataclass(frozen=True)
class FreelancerSearchFilters:
    search: str | None = None

    skill_ids: tuple[str, ...] = ()

    city: str | None = None

    availability_status: str | None = "AVAILABLE"

    min_price: int | None = None
    max_price: int | None = None

    min_experience_count: int | None = None

    min_rating: float | None = None
