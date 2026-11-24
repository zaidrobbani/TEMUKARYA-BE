import pytest

from app.core.exceptions import BadRequestError, ConflictError
from app.core.unit_of_work import UnitOfWork

from app.modules.profiles.application.dto import (
    CreateUmkmProfileInput,
)
from app.modules.profiles.application.use_cases import (
    CreateUmkmProfile,
)


# Repository palsu untuk pengujian tanpa MySQL
class FakeUmkmRepository:

    def __init__(self):
        self.profiles = {}

    def get_by_user_id(self, user_id):
        return self.profiles.get(user_id)

    def add(self, profile):
        self.profiles[profile.user_id] = profile
        return profile


# Simulasi transaksi database
class FakeUnitOfWork(UnitOfWork):

    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True


# Membuat contoh input profil UMKM
def make_input(**overrides):
    data = {
        "business_name": "Kopi Malang",
        "business_category": "Food & Beverage",
        "business_address": "Jl. Soekarno Hatta",
        "city": "Malang",
    }

    return CreateUmkmProfileInput(**(data | overrides))


# TEST 1: Berhasil membuat profil UMKM
def test_create_umkm_profile_success():
    repo = FakeUmkmRepository()
    uow = FakeUnitOfWork()

    result = CreateUmkmProfile(repo, uow).execute(
        "user-uuid-test",
        make_input(),
    )

    assert result.business_name == "Kopi Malang"
    assert result.city == "Malang"
    assert uow.committed is True


# TEST 2: Menolak profil duplikat
def test_create_umkm_profile_duplicate():
    repo = FakeUmkmRepository()
    uow = FakeUnitOfWork()

    use_case = CreateUmkmProfile(repo, uow)

    use_case.execute("user-uuid-test", make_input())
    uow.committed = False

    with pytest.raises(ConflictError):
        use_case.execute("user-uuid-test", make_input())

    assert uow.committed is False


# TEST 3: Menolak nama usaha kosong
def test_create_umkm_profile_empty_name():
    repo = FakeUmkmRepository()
    uow = FakeUnitOfWork()

    with pytest.raises(BadRequestError):
        CreateUmkmProfile(repo, uow).execute(
            "user-uuid-test",
            make_input(business_name="   "),
        )

    assert uow.committed is False


# TEST 4: Menolak nama usaha lebih dari 160 karakter
def test_create_umkm_profile_name_too_long():
    repo = FakeUmkmRepository()
    uow = FakeUnitOfWork()

    with pytest.raises(BadRequestError):
        CreateUmkmProfile(repo, uow).execute(
            "user-uuid-test",
            make_input(business_name="X" * 161),
        )

    assert uow.committed is False