import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.core.tokens import TokenClaims
from app.modules.users.domain.entities import User, UserRole


class LoginPortal(StrEnum):
    MOBILE_APP = "MOBILE_APP"
    ADMIN_DASHBOARD = "ADMIN_DASHBOARD"


PORTAL_ROLES: dict[LoginPortal, frozenset[UserRole]] = {
    LoginPortal.MOBILE_APP: frozenset({UserRole.UMKM, UserRole.FREELANCER}),
    LoginPortal.ADMIN_DASHBOARD: frozenset({UserRole.ADMIN}),
}


class AuthActionPurpose(StrEnum):
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PASSWORD_RESET = "PASSWORD_RESET"


EMAIL_VERIFICATION_TTL = timedelta(hours=24)
PASSWORD_RESET_TTL = timedelta(minutes=30)
EMAIL_RESEND_COOLDOWN = timedelta(seconds=60)


def hash_action_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


@dataclass(frozen=True)
class AuthSession:
    user: User
    claims: TokenClaims


@dataclass(frozen=True)
class AuthActionToken:
    user_id: str
    purpose: AuthActionPurpose
    token_hash: str
    expires_at: datetime
    created_at: datetime
    used_at: datetime | None = None
    id: str | None = None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at
