from dataclasses import dataclass
from datetime import date

from app.modules.profiles.domain.entities import Portfolio


@dataclass(frozen=True)
class CreateUmkmProfileInput:
    business_name: str
    business_category: str
    business_address: str
    city: str



@dataclass(frozen=True)
class CreateFreelancerProfileInput:
    professional_title: str
    city: str
    bio: str | None = None
    service_price_min: int | None = None
    service_price_max: int | None = None


@dataclass(frozen=True)
class UpdateUmkmProfileInput(CreateUmkmProfileInput):
    """Replace editable fields; identity is supplied separately by authentication."""


@dataclass(frozen=True, kw_only=True)
class UpdateFreelancerProfileInput(CreateFreelancerProfileInput):
    availability_status: str


@dataclass(frozen=True)
class SetFreelancerSkillsInput:
    skill_ids: list[str]


@dataclass(frozen=True)
class CreateFreelancerExperienceInput:
    job_title: str
    organization_name: str
    description: str
    start_date: date
    end_date: date | None = None


@dataclass(frozen=True)
class UpdateFreelancerExperienceInput(CreateFreelancerExperienceInput):
    """Penggantian seluruh isi experience, tanpa ID atau ownership dari body."""


@dataclass(frozen=True)
class CreatePortfolioInput:
    title: str
    description: str
    project_url: str | None = None


@dataclass(frozen=True)
class UpdatePortfolioInput(CreatePortfolioInput):
    """Penggantian metadata tanpa ownership atau tanggal audit dari client."""


@dataclass(frozen=True)
class PortfolioPage:
    items: list[Portfolio]
    limit: int
    offset: int
    has_more: bool
