from abc import ABC, abstractmethod

from app.modules.users.domain.entities import User


class UserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def add(self, user: User) -> User: ...
