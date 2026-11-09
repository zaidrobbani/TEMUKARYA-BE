from uuid import uuid4

import pytest

from app.core.security import ScryptPasswordHasher
from app.modules.users.application.dto import CreateAdminInput, RegisterUserInput
from app.modules.users.application.use_cases import CreateAdmin, GetUser, RegisterUser
from app.modules.users.domain.entities import User, UserRole
from app.modules.users.domain.exceptions import (
    EmailAlreadyRegisteredError,
    RoleNotRegistrableError,
    UserAccessDeniedError,
    UserNotFoundError,
)
from tests.fakes import FakeUnitOfWork, FakeUserRepository


def make_input(**overrides) -> RegisterUserInput:
    data = {
        "name": " Budi ",
        "email": "Budi@Mail.com ",
        "password": "rahasia123",
        "role": UserRole.UMKM,
        "phone_number": "+6281234567890",
    }
    return RegisterUserInput(**(data | overrides))


def make_user(repo: FakeUserRepository, role: UserRole = UserRole.UMKM) -> User:
    return repo.add(User(name="User", email=f"{uuid4()}@mail.com", password_hash="x", role=role))


@pytest.mark.parametrize("role", [UserRole.UMKM, UserRole.FREELANCER])
def test_register_user_normalizes_input_hashes_password_and_commits(role):
    repo, uow, hasher = FakeUserRepository(), FakeUnitOfWork(), ScryptPasswordHasher()

    user = RegisterUser(repo, hasher, uow).execute(make_input(role=role))

    assert repo.get_by_id(user.id) == user
    assert user.name == "Budi"
    assert user.email == "budi@mail.com"
    assert user.role == role
    assert user.phone_number == "+6281234567890"
    assert user.password_hash != "rahasia123"
    assert hasher.verify("rahasia123", user.password_hash)
    assert uow.committed


def test_register_user_rejects_duplicate_email_case_insensitive():
    repo, uow = FakeUserRepository(), FakeUnitOfWork()
    use_case = RegisterUser(repo, ScryptPasswordHasher(), uow)
    use_case.execute(make_input())

    with pytest.raises(EmailAlreadyRegisteredError):
        use_case.execute(make_input(email="BUDI@mail.com"))
    assert uow.commits == 1
    assert len(repo.users) == 1


def test_register_user_rejects_admin_role_without_touching_repository():
    repo, uow = FakeUserRepository(), FakeUnitOfWork()

    with pytest.raises(RoleNotRegistrableError):
        RegisterUser(repo, ScryptPasswordHasher(), uow).execute(make_input(role=UserRole.ADMIN))
    assert repo.users == {}
    assert not uow.committed


def test_create_admin_sets_admin_role():
    repo, uow = FakeUserRepository(), FakeUnitOfWork()

    admin = CreateAdmin(repo, ScryptPasswordHasher(), uow).execute(
        CreateAdminInput(name="Admin", email="Admin@Temukarya.id", password="rahasia123")
    )

    assert admin.role == UserRole.ADMIN
    assert admin.email == "admin@temukarya.id"
    assert uow.committed


def test_create_admin_rejects_duplicate_email():
    repo, uow = FakeUserRepository(), FakeUnitOfWork()
    RegisterUser(repo, ScryptPasswordHasher(), uow).execute(make_input())

    with pytest.raises(EmailAlreadyRegisteredError):
        CreateAdmin(repo, ScryptPasswordHasher(), uow).execute(
            CreateAdminInput(name="Admin", email="budi@mail.com", password="rahasia123")
        )


def test_get_user_returns_own_data():
    repo = FakeUserRepository()
    user = make_user(repo)

    assert GetUser(repo).execute(user.id, requester=user) == user


def test_get_user_allows_admin_to_read_other_user():
    repo = FakeUserRepository()
    user, admin = make_user(repo), make_user(repo, UserRole.ADMIN)

    assert GetUser(repo).execute(user.id, requester=admin) == user


@pytest.mark.parametrize("requester_role", [UserRole.UMKM, UserRole.FREELANCER])
def test_get_user_denies_reading_other_user(requester_role):
    repo = FakeUserRepository()
    other, requester = make_user(repo), make_user(repo, requester_role)

    with pytest.raises(UserAccessDeniedError):
        GetUser(repo).execute(other.id, requester=requester)


def test_get_user_denies_non_admin_probing_unknown_id():
    repo = FakeUserRepository()
    requester = make_user(repo)

    with pytest.raises(UserAccessDeniedError):
        GetUser(repo).execute(str(uuid4()), requester=requester)


def test_get_user_raises_not_found_for_admin():
    repo = FakeUserRepository()
    admin = make_user(repo, UserRole.ADMIN)

    with pytest.raises(UserNotFoundError):
        GetUser(repo).execute(str(uuid4()), requester=admin)
