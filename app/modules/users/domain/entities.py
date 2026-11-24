from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class UserRole(StrEnum):
    UMKM = "UMKM"
    FREELANCER = "FREELANCER"
    ADMIN = "ADMIN"


SELF_REGISTRABLE_ROLES = frozenset({UserRole.UMKM, UserRole.FREELANCER})


@dataclass
class User:
    name: str
    email: str
    password_hash: str
    role: UserRole
    phone_number: str | None = None
    profile_image_url: str | None = None
    email_verified_at: datetime | None = None
    password_changed_at: datetime | None = None
    terms_accepted_at: datetime | None = None
    id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
