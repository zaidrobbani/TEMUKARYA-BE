from dataclasses import dataclass

from datetime import date, datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class UmkmProfile:
    user_id: str
    business_name: str
    business_category: str
    business_address: str
    city: str


@dataclass(frozen=True)
class FreelancerProfile:
    user_id: str
    professional_title: str
    city: str
    bio: str | None = None
    service_price_min: int | None = None
    service_price_max: int | None = None
    availability_status: str = "AVAILABLE"


@dataclass(frozen=True)
class FreelancerExperience:
    id: str
    freelancer_id: str
    job_title: str
    organization_name: str
    description: str
    start_date: date
    end_date: date | None = None


@dataclass(frozen=True)
class Portfolio:
    id: str
    freelancer_id: str
    title: str
    description: str
    project_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
