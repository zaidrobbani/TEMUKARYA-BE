
import pytest

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
)
from app.core.unit_of_work import UnitOfWork

from app.modules.profiles.application.dto import (
    CreateFreelancerProfileInput,
)
from app.modules.profiles.application.use_cases import (
    CreateFreelancerProfile,
)


class FakeFreelancerRepository:

    def __init__(self):
        self.profiles = {}

    def get_by_user_id(self, user_id):
        return self.profiles.get(user_id)

    def add(self, profile):
        self.profiles[profile.user_id] = profile
        return profile


class FakeUnitOfWork(UnitOfWork):

    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True


def make_input(**overrides):
    data = {
        "professional_title": "UI/UX Designer",
        "city": "Malang",
        "bio": "Desainer aplikasi mobile",
        "service_price_min": 150000,
        "service_price_max": 1000000,
    }

    return CreateFreelancerProfileInput(
        **(data | overrides)
    )


def test_create_freelancer_success():
    repo = FakeFreelancerRepository()
    uow = FakeUnitOfWork()

    result = CreateFreelancerProfile(
        repo, uow
    ).execute(
        "user-uuid-test",
        make_input(),
    )

    assert result.professional_title == "UI/UX Designer"
    assert result.city == "Malang"
    assert result.availability_status == "AVAILABLE"
    assert uow.committed is True


def test_create_freelancer_duplicate():
    repo = FakeFreelancerRepository()
    uow = FakeUnitOfWork()
    use_case = CreateFreelancerProfile(repo, uow)

    use_case.execute("user-uuid-test", make_input())
    uow.committed = False

    with pytest.raises(ConflictError):
        use_case.execute(
            "user-uuid-test",
            make_input(),
        )

    assert uow.committed is False


def test_create_freelancer_empty_title():
    repo = FakeFreelancerRepository()
    uow = FakeUnitOfWork()

    with pytest.raises(BadRequestError):
        CreateFreelancerProfile(repo, uow).execute(
            "user-uuid-test",
            make_input(professional_title="   "),
        )

    assert uow.committed is False


def test_create_freelancer_negative_price():
    repo = FakeFreelancerRepository()
    uow = FakeUnitOfWork()

    with pytest.raises(BadRequestError):
        CreateFreelancerProfile(repo, uow).execute(
            "user-uuid-test",
            make_input(service_price_min=-10000),
        )

    assert uow.committed is False


def test_create_freelancer_invalid_price_range():
    repo = FakeFreelancerRepository()
    uow = FakeUnitOfWork()

    with pytest.raises(BadRequestError):
        CreateFreelancerProfile(repo, uow).execute(
            "user-uuid-test",
            make_input(
                service_price_min=2000000,
                service_price_max=500000,
            ),
        )

    assert uow.committed is False



# TEST 6: Kota tidak boleh kosong
def test_create_freelancer_empty_city():
    repo = FakeFreelancerRepository()
    uow = FakeUnitOfWork()

    with pytest.raises(BadRequestError):
        CreateFreelancerProfile(repo, uow).execute(
            "user-uuid-test",
            make_input(city="   "),
        )

    assert uow.committed is False


# TEST 7: Harga maksimum tidak boleh negatif
def test_create_freelancer_negative_max_price():
    repo = FakeFreelancerRepository()
    uow = FakeUnitOfWork()

    with pytest.raises(BadRequestError):
        CreateFreelancerProfile(repo, uow).execute(
            "user-uuid-test",
            make_input(service_price_max=-50000),
        )

    assert uow.committed is False


# TEST 8: Profesi maksimal 150 karakter
def test_create_freelancer_title_too_long():
    repo = FakeFreelancerRepository()
    uow = FakeUnitOfWork()

    with pytest.raises(BadRequestError):
        CreateFreelancerProfile(repo, uow).execute(
            "user-uuid-test",
            make_input(professional_title="A" * 151),
        )

    assert uow.committed is False


# TEST 9: Harga jasa boleh tidak diisi
def test_create_freelancer_without_prices():
    repo = FakeFreelancerRepository()
    uow = FakeUnitOfWork()

    result = CreateFreelancerProfile(repo, uow).execute(
        "user-uuid-test",
        make_input(
            service_price_min=None,
            service_price_max=None,
        ),
    )

    assert result.service_price_min is None
    assert result.service_price_max is None
    assert uow.committed is True


# TEST 10: Spasi berlebihan dibersihkan
def test_create_freelancer_trims_whitespace():
    repo = FakeFreelancerRepository()
    uow = FakeUnitOfWork()

    result = CreateFreelancerProfile(repo, uow).execute(
        "user-uuid-test",
        make_input(
            professional_title="  UI/UX Designer  ",
            city="  Malang  ",
        ),
    )

    assert result.professional_title == "UI/UX Designer"
    assert result.city == "Malang"
    assert uow.committed is True