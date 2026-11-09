from abc import ABC, abstractmethod
from datetime import datetime

from app.modules.users.domain.entities import User


class UserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: str) -> User | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def add(self, user: User) -> User: ...

    @abstractmethod
    def mark_email_verified(self, user_id: str, verified_at: datetime) -> None: ...

    @abstractmethod
    def update_password(self, user_id: str, password_hash: str, changed_at: datetime) -> None: ...
