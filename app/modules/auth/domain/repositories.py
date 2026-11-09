from abc import ABC, abstractmethod
from datetime import datetime

from app.modules.auth.domain.entities import AuthActionPurpose, AuthActionToken


class RevokedTokenRepository(ABC):
    @abstractmethod
    def add(self, jti: str, user_id: str, expires_at: datetime) -> None: ...

    @abstractmethod
    def exists(self, jti: str) -> bool: ...


class AuthActionTokenRepository(ABC):
    @abstractmethod
    def add(self, token: AuthActionToken) -> None: ...

    @abstractmethod
    def get_by_hash(self, token_hash: str, purpose: AuthActionPurpose) -> AuthActionToken | None: ...

    @abstractmethod
    def latest_created_at(self, user_id: str, purpose: AuthActionPurpose) -> datetime | None: ...

    @abstractmethod
    def invalidate_active(self, user_id: str, purpose: AuthActionPurpose, at: datetime) -> None: ...

    @abstractmethod
    def consume(self, token_id: str, at: datetime) -> bool:
        """Tandai terpakai secara atomik. False berarti token sudah dipakai request lain."""
