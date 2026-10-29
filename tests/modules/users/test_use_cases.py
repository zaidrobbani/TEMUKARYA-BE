from dataclasses import replace
from uuid import uuid4

import pytest

from app.core.security import ScryptPasswordHasher
from app.core.unit_of_work import UnitOfWork
from app.modules.users.application.dto import RegisterUserInput
from app.modules.users.application.use_cases import GetUser, RegisterUser
from app.modules.users.domain.entities import User, UserRole
from app.modules.users.domain.exceptions import EmailAlreadyRegisteredError, UserNotFoundError
from app.modules.users.domain.repositories import UserRepository


class FakeUserRepository(UserRepository):
    def __init__(self):
        self.users: dict[str, User] = {}

    def get_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    def add(self, user: User) -> User:
        saved = replace(user, id=str(uuid4()))
        self.users[saved.id] = saved
        return saved


class FakeUnitOfWork(UnitOfWork):
    def __init__(self):
        self.committed = False

    def commit(self) -> None:
        self.committed = True


def make_input(**overrides) -> RegisterUserInput:
    data = {"name": "Budi", "email": "Budi@Mail.com ", "password": "rahasia123", "role": UserRole.UMKM}
    return RegisterUserInput(**(data | overrides))


def test_register_user_normalizes_email_hashes_password_and_commits():
    repo, uow, hasher = FakeUserRepository(), FakeUnitOfWork(), ScryptPasswordHasher()

    user = RegisterUser(repo, hasher, uow).execute(make_input())

    assert repo.get_by_id(user.id) == user
    assert user.email == "budi@mail.com"
    assert hasher.verify("rahasia123", user.password_hash)
    assert uow.committed


def test_register_user_rejects_duplicate_email():
    repo, uow = FakeUserRepository(), FakeUnitOfWork()
    use_case = RegisterUser(repo, ScryptPasswordHasher(), uow)
    use_case.execute(make_input())
    uow.committed = False

    with pytest.raises(EmailAlreadyRegisteredError):
        use_case.execute(make_input(email="budi@mail.com"))
    assert not uow.committed


def test_get_user_raises_when_missing():
    with pytest.raises(UserNotFoundError):
        GetUser(FakeUserRepository()).execute(str(uuid4()))
