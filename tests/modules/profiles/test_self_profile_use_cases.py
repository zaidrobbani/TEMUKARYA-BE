from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.unit_of_work import UnitOfWork
from app.modules.profiles.application.dto import (
    CreateFreelancerProfileInput, UpdateFreelancerProfileInput, UpdateUmkmProfileInput,
)
from app.modules.profiles.application.self_profile_use_cases import (
    GetFreelancerProfile, GetUmkmProfile, UpdateFreelancerProfile, UpdateUmkmProfile,
)
from app.modules.profiles.application.use_cases import CreateFreelancerProfile
from app.modules.profiles.domain.entities import FreelancerProfile, UmkmProfile
from app.modules.profiles.domain.repositories import FreelancerProfileRepository, UmkmProfileRepository


CASES = [
    (GetUmkmProfile, UpdateUmkmProfile, UmkmProfileRepository,
     UmkmProfile("owner", "Old", "Food", "Street", "Malang"),
     UpdateUmkmProfileInput(" New ", " Food ", " Street ", " Malang ")),
    (GetFreelancerProfile, UpdateFreelancerProfile, FreelancerProfileRepository,
     FreelancerProfile("owner", "Old", "Malang", bio="Old bio"),
     UpdateFreelancerProfileInput(" New ", " Malang ", availability_status=" AVAILABLE ")),
]


@pytest.mark.parametrize("getter,updater,spec,original,data", CASES)
def test_self_profile_get_replace_uses_authenticated_identity_and_commit(getter, updater, spec, original, data):
    repository, uow = MagicMock(spec=spec), MagicMock(spec=UnitOfWork)
    repository.get_by_user_id.return_value = original
    repository.update.side_effect = lambda profile: profile
    assert getter(repository).execute("owner") == original
    result = updater(repository, uow).execute("owner", data)
    assert result.user_id == "owner" and result.city == "Malang"
    assert all(call.args == ("owner",) for call in repository.get_by_user_id.call_args_list)
    repository.update.assert_called_once_with(result)
    uow.commit.assert_called_once_with()
    if isinstance(result, FreelancerProfile):
        assert result.bio is result.service_price_min is result.service_price_max is None
        assert result.availability_status == "AVAILABLE"


@pytest.mark.parametrize("getter,updater,spec,original,data", CASES)
def test_self_profile_missing_and_concurrent_removal_never_commit(getter, updater, spec, original, data):
    repository, uow = MagicMock(spec=spec), MagicMock(spec=UnitOfWork)
    repository.get_by_user_id.return_value = None
    with pytest.raises(NotFoundError):
        getter(repository).execute("missing")
    with pytest.raises(NotFoundError):
        updater(repository, uow).execute("missing", data)
    repository.update.assert_not_called()
    repository.get_by_user_id.return_value = original
    repository.update.return_value = None
    with pytest.raises(NotFoundError):
        updater(repository, uow).execute("owner", data)
    uow.commit.assert_not_called()


@pytest.mark.parametrize("getter,updater,spec,original,data", CASES)
@pytest.mark.parametrize("stage", ["update", "commit"])
def test_self_profile_database_failures_propagate(getter, updater, spec, original, data, stage):
    repository, uow = MagicMock(spec=spec), MagicMock(spec=UnitOfWork)
    repository.get_by_user_id.return_value = original
    repository.update.side_effect = lambda profile: profile
    if stage == "update":
        repository.update.side_effect = RuntimeError("database failed")
    else:
        uow.commit.side_effect = RuntimeError("database failed")
    with pytest.raises(RuntimeError, match="database failed"):
        updater(repository, uow).execute("owner", data)
    if stage == "update":
        uow.commit.assert_not_called()


@pytest.mark.parametrize("field,limit", [
    ("business_name", 160), ("business_category", 100), ("business_address", 300), ("city", 100),
])
@pytest.mark.parametrize("invalid", ["blank", "too-long", "invalid-unicode"])
def test_umkm_replace_validates_every_text_column(field, limit, invalid):
    repository, uow = MagicMock(spec=UmkmProfileRepository), MagicMock(spec=UnitOfWork)
    value = {"blank": "  ", "too-long": "a" * (limit + 1), "invalid-unicode": "\ud800"}[invalid]
    with pytest.raises(BadRequestError):
        UpdateUmkmProfile(repository, uow).execute("owner", replace(CASES[0][4], **{field: value}))
    repository.update.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.parametrize("values", [
    {"professional_title": " "}, {"professional_title": "a" * 151},
    {"city": " "}, {"city": "a" * 101}, {"availability_status": " "},
    {"availability_status": "a" * 26}, {"bio": "a" * 65536},
    {"bio": "\U0001f600" * 16384}, {"bio": "\ud800"},
    {"service_price_min": -1}, {"service_price_max": -1},
    {"service_price_min": 2**64}, {"service_price_max": 2**64},
    {"service_price_min": True}, {"service_price_max": 1.2},
    {"service_price_min": 200, "service_price_max": 100},
])
def test_freelancer_replace_rejects_invalid_fields_before_write(values):
    repository, uow = MagicMock(spec=FreelancerProfileRepository), MagicMock(spec=UnitOfWork)
    with pytest.raises(BadRequestError):
        UpdateFreelancerProfile(repository, uow).execute("owner", replace(CASES[1][4], **values))
    repository.update.assert_not_called()
    uow.commit.assert_not_called()


def test_self_profile_exact_column_limits_and_optional_normalization():
    repository, uow = MagicMock(), MagicMock(spec=UnitOfWork)
    repository.update.side_effect = lambda profile: profile
    umkm = UpdateUmkmProfile(repository, uow).execute(
        "owner", UpdateUmkmProfileInput("a" * 160, "a" * 100, "a" * 300, "a" * 100),
    )
    assert len(umkm.business_address) == 300
    data = UpdateFreelancerProfileInput(
        "a" * 150, "a" * 100, bio="\U0001f600" * 16383 + "abc",
        service_price_min=0, service_price_max=2**64 - 1, availability_status="a" * 25,
    )
    result = UpdateFreelancerProfile(repository, uow).execute("owner", data)
    assert len(result.bio.encode("utf-8")) == 65535 and result.service_price_max == 2**64 - 1
    assert UpdateFreelancerProfile(repository, uow).execute("owner", replace(data, bio=" ")).bio is None


@pytest.mark.parametrize("field", ["service_price_min", "service_price_max"])
def test_create_freelancer_uint64_overflow_regression(field):
    # Previously the application layer accepted values MySQL cannot store.
    repository, uow = MagicMock(spec=FreelancerProfileRepository), MagicMock(spec=UnitOfWork)
    repository.get_by_user_id.return_value = None
    with pytest.raises(BadRequestError):
        CreateFreelancerProfile(repository, uow).execute(
            "owner", CreateFreelancerProfileInput("Designer", "Malang", **{field: 2**64}),
        )
    repository.add.assert_not_called()
    uow.commit.assert_not_called()
