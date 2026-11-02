
from dataclasses import dataclass
from datetime import date, datetime


# ============================================================
# 1. FREELANCER SKILL
# ============================================================

@dataclass(frozen=True)
class FreelancerSkill:
    """
    Representasi satu keahlian Freelancer.

    Sumber:
    freelancer_skills JOIN skills
    """

    id: str
    name: str


# ============================================================
# 2. FREELANCER WORK EXPERIENCE
# ============================================================

@dataclass(frozen=True)
class FreelancerWorkExperience:
    """
    Representasi pengalaman kerja Freelancer.

    Sumber:
    freelancer_experiences
    """

    id: str
    job_title: str
    organization_name: str
    description: str
    start_date: date
    end_date: date | None = None


# ============================================================
# 3. FREELANCER PORTFOLIO
# ============================================================

@dataclass(frozen=True)
class FreelancerPortfolio:
    """
    Representasi portofolio Freelancer.

    Sumber:
    portfolios
    """

    id: str
    title: str
    description: str
    project_url: str | None = None


# ============================================================
# 4. FREELANCER REVIEW
# ============================================================

@dataclass(frozen=True)
class FreelancerReview:
    """
    Representasi ulasan terhadap Freelancer.

    Sumber:
    freelancer_reviews melalui project_agreements
    """

    id: str
    project_id: str
    rating: int
    review_text: str | None = None
    created_at: datetime | None = None


# ============================================================
# 5. FREELANCER SUMMARY
# ============================================================

@dataclass(frozen=True)
class FreelancerSummary:
    """
    Data ringkas Freelancer untuk halaman pencarian.

    Tidak memuat informasi sensitif seperti
    email atau password_hash.
    """

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


# ============================================================
# 6. FREELANCER DETAIL
# ============================================================

@dataclass(frozen=True)
class FreelancerDetail(FreelancerSummary):
    """
    Data detail profil Freelancer.

    Mewarisi seluruh field dari FreelancerSummary,
    kemudian menambahkan data detail.
    """

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


# ============================================================
# 7. FREELANCER SEARCH FILTERS
# ============================================================

@dataclass(frozen=True)
class FreelancerSearchFilters:
    """
    Parameter pencarian dan filter Freelancer.

    Validasi akan dilakukan pada Application Layer.
    """

    search: str | None = None

    skill_ids: tuple[str, ...] = ()

    city: str | None = None

    availability_status: str | None = "AVAILABLE"

    min_price: int | None = None
    max_price: int | None = None

    min_experience_count: int | None = None

    min_rating: float | None = None