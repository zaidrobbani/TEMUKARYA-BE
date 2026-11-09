from dataclasses import replace
from datetime import date
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
)

from app.modules.profiles.application.dto import (
    CreateFreelancerExperienceInput,
    UpdateFreelancerExperienceInput,
)

from app.modules.profiles.application.use_cases import (
    CreateFreelancerExperience,
    GetFreelancerExperiences,
    UpdateFreelancerExperience,
    DeleteFreelancerExperience,
)

from app.modules.profiles.domain.entities import FreelancerExperience
from app.modules.profiles.domain.repositories import FreelancerExperienceRepository
from app.core.unit_of_work import UnitOfWork


# HELPER: DATA EXPERIENCE YANG VALID

def valid_experience_input():
    return CreateFreelancerExperienceInput(
        job_title="Graphic Designer",
        organization_name="Studio Kreatif ABC",
        description="Membuat desain branding UMKM",
        start_date=date(2024, 1, 15),
        end_date=date(2025, 12, 20),
    )


# HELPER: MEMBUAT USE CASE UNTUK TEST

def make_use_case(profile_exists=True):
    profile_repo = MagicMock()
    experience_repo = MagicMock()
    uow = MagicMock()

    profile_repo.get_by_user_id.return_value = (
        object() if profile_exists else None
    )

    use_case = CreateFreelancerExperience(
        profile_repository=profile_repo,
        experience_repository=experience_repo,
        uow=uow,
    )

    return (
        use_case,
        profile_repo,
        experience_repo,
        uow,
    )


# TEST 1: CREATE EXPERIENCE BERHASIL

def test_create_experience_success():
    use_case, profile_repo, experience_repo, uow = (
        make_use_case()
    )

    data = valid_experience_input()

    result = use_case.execute(
        freelancer_id="freelancer-test-uuid",
        data=data,
    )

    assert result.freelancer_id == "freelancer-test-uuid"
    assert result.job_title == "Graphic Designer"
    assert result.organization_name == "Studio Kreatif ABC"
    assert result.description == "Membuat desain branding UMKM"

    # Memastikan ID yang dibuat berbentuk UUID valid
    UUID(result.id)

    profile_repo.get_by_user_id.assert_called_once_with(
        "freelancer-test-uuid"
    )

    experience_repo.add.assert_called_once_with(result)
    uow.commit.assert_called_once()


# TEST 2: PROFIL FREELANCER TIDAK ADA

def test_create_experience_profile_not_found():
    use_case, _, experience_repo, uow = make_use_case(
        profile_exists=False
    )

    with pytest.raises(NotFoundError):
        use_case.execute(
            freelancer_id="freelancer-test-uuid",
            data=valid_experience_input(),
        )

    experience_repo.add.assert_not_called()
    uow.commit.assert_not_called()


# TEST 3-8: INPUT TIDAK VALID

@pytest.mark.parametrize(
    "changes",
    [
        {"job_title": "   "},
        {"job_title": "A" * 151},
        {"organization_name": "   "},
        {"organization_name": "A" * 161},
        {"description": "   "},
        {
            "start_date": date(2025, 8, 1),
            "end_date": date(2024, 12, 1),
        },
    ],
)
def test_create_experience_invalid_input(changes):
    use_case, _, experience_repo, uow = make_use_case()

    data = replace(
        valid_experience_input(),
        **changes,
    )

    with pytest.raises(BadRequestError):
        use_case.execute(
            freelancer_id="freelancer-test-uuid",
            data=data,
        )

    # Data tidak boleh disimpan jika validasi gagal
    experience_repo.add.assert_not_called()
    uow.commit.assert_not_called()


# TEST 9: FREELANCER MASIH BEKERJA

def test_create_experience_ongoing():
    use_case, _, experience_repo, uow = make_use_case()

    data = replace(
        valid_experience_input(),
        end_date=None,
    )

    result = use_case.execute(
        freelancer_id="freelancer-test-uuid",
        data=data,
    )

    assert result.end_date is None
    experience_repo.add.assert_called_once()
    uow.commit.assert_called_once()


# TEST 10: SPASI BERLEBIH DIBERSIHKAN

def test_create_experience_trims_text():
    use_case, _, experience_repo, uow = make_use_case()

    data = replace(
        valid_experience_input(),
        job_title="  Graphic Designer  ",
        organization_name="  Studio Kreatif ABC  ",
        description="  Membuat desain branding UMKM  ",
    )

    result = use_case.execute(
        freelancer_id="freelancer-test-uuid",
        data=data,
    )

    assert result.job_title == "Graphic Designer"
    assert result.organization_name == "Studio Kreatif ABC"
    assert result.description == "Membuat desain branding UMKM"

    experience_repo.add.assert_called_once()
    uow.commit.assert_called_once()


def update_input(**changes):
    return replace(
        UpdateFreelancerExperienceInput(
            job_title="Graphic Designer",
            organization_name="Studio Kreatif ABC",
            description="Membuat desain branding UMKM",
            start_date=date(2024, 1, 15),
            end_date=date(2025, 12, 20),
        ),
        **changes,
    )


@pytest.mark.parametrize("empty", [False, True])
def test_list_experiences_scoped_to_current_freelancer(empty):
    repository = MagicMock(spec=FreelancerExperienceRepository)
    experiences = [] if empty else [
        FreelancerExperience(
            id="experience-1", freelancer_id="owner-1",
            **vars(update_input()),
        )
    ]
    repository.list_by_freelancer_id.return_value = experiences

    result = GetFreelancerExperiences(repository).execute("owner-1")

    assert result == experiences
    repository.list_by_freelancer_id.assert_called_once_with("owner-1")


@pytest.mark.parametrize("end_date", [None, date(2024, 1, 15), date(2025, 12, 20)])
def test_update_experience_success_and_trimming(end_date):
    repository = MagicMock(spec=FreelancerExperienceRepository)
    repository.update.return_value = True
    uow = MagicMock(spec=UnitOfWork)
    data = update_input(
        job_title="  Designer  ", organization_name="  Studio  ",
        description="  Branding  ", end_date=end_date,
    )

    result = UpdateFreelancerExperience(repository, uow).execute(
        freelancer_id="owner-1", experience_id="experience-1", data=data,
    )

    assert result == FreelancerExperience(
        id="experience-1", freelancer_id="owner-1", job_title="Designer",
        organization_name="Studio", description="Branding",
        start_date=date(2024, 1, 15), end_date=end_date,
    )
    repository.update.assert_called_once_with(result)
    uow.commit.assert_called_once()


@pytest.mark.parametrize("changes", [
    {"job_title": ""}, {"job_title": "   "}, {"job_title": "A" * 151},
    {"organization_name": ""}, {"organization_name": "   "},
    {"organization_name": "A" * 161},
    {"description": ""}, {"description": "   "},
    {"end_date": date(2023, 1, 1)},
])
def test_update_experience_invalid_input_does_not_write(changes):
    repository = MagicMock(spec=FreelancerExperienceRepository)
    uow = MagicMock(spec=UnitOfWork)

    with pytest.raises(BadRequestError):
        UpdateFreelancerExperience(repository, uow).execute(
            "owner-1", "experience-1", update_input(**changes),
        )

    repository.update.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_experience_not_found_does_not_commit(operation):
    repository = MagicMock(spec=FreelancerExperienceRepository)
    repository.update.return_value = False
    repository.delete.return_value = False
    uow = MagicMock(spec=UnitOfWork)

    with pytest.raises(NotFoundError, match="Pengalaman kerja tidak ditemukan"):
        if operation == "update":
            UpdateFreelancerExperience(repository, uow).execute(
                "owner-1", "missing-or-foreign", update_input(),
            )
        else:
            DeleteFreelancerExperience(repository, uow).execute(
                "owner-1", "missing-or-foreign",
            )

    uow.commit.assert_not_called()


def test_delete_experience_success():
    repository = MagicMock(spec=FreelancerExperienceRepository)
    repository.delete.return_value = True
    uow = MagicMock(spec=UnitOfWork)

    result = DeleteFreelancerExperience(repository, uow).execute(
        "owner-1", "experience-1",
    )

    assert result is None
    repository.delete.assert_called_once_with("experience-1", "owner-1")
    uow.commit.assert_called_once()


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_repository_failure_does_not_commit(operation):
    repository = MagicMock(spec=FreelancerExperienceRepository)
    getattr(repository, operation).side_effect = RuntimeError("storage unavailable")
    uow = MagicMock(spec=UnitOfWork)

    with pytest.raises(RuntimeError, match="storage unavailable"):
        if operation == "update":
            UpdateFreelancerExperience(repository, uow).execute(
                "owner-1", "experience-1", update_input(),
            )
        else:
            DeleteFreelancerExperience(repository, uow).execute("owner-1", "experience-1")

    uow.commit.assert_not_called()
