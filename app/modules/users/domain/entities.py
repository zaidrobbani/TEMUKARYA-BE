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
    id: int | None = None
    created_at: datetime | None = None
