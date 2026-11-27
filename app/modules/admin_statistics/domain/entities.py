from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class AdminActor:
    user_id: str
    role: str


@dataclass(frozen=True, slots=True)
class AdminUserSummary:
    id: str
    name: str
    email: str
    role: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AdminUMKMProfile:
    business_name: str
    business_category: str
    business_address: str
    city: str


@dataclass(frozen=True, slots=True)
class AdminFreelancerProfile:
    professional_title: str
    bio: str | None
    city: str

    service_price_min: int | None
    service_price_max: int | None

    availability_status: str


@dataclass(frozen=True, slots=True)
class AdminUserDetail:
    user: AdminUserSummary

    umkm_profile: AdminUMKMProfile | None = None

    freelancer_profile: AdminFreelancerProfile | None = None


@dataclass(frozen=True, slots=True)
class AdminProjectSummary:
    id: str
    title: str
    category_id: str

    umkm_id: str
    umkm_name: str | None

    assigned_freelancer_id: str | None
    assigned_freelancer_name: str | None

    budget: int
    deadline: date
    status: str

    created_at: datetime


@dataclass(frozen=True, slots=True)
class AdminProjectDetail:
    project: AdminProjectSummary

    description: str
    agreed_price: int | None

    published_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class AdminSystemStatistics:
    total_umkm: int
    total_freelancers: int

    total_projects: int
    completed_projects: int

    total_transactions: int
    platform_income: int
