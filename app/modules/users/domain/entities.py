from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class UserRole(StrEnum):
    UMKM = "umkm"
    FREELANCER = "freelancer"


@dataclass
class User:
    name: str
    email: str
    password_hash: str
    role: UserRole
    phone_number: str | None = None
    profile_image_url: str | None = None
    id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
