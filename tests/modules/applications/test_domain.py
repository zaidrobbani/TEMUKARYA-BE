from dataclasses import FrozenInstanceError
from datetime import datetime
from uuid import uuid4

import pytest

from app.modules.applications.domain.entities import (
    APPLICATION_SUBMITTED,
    ProjectApplication,
)

from app.modules.applications.domain.repositories import (
    ApplicationRepository,
)


# TEST DATA FACTORY
def make_application():
    return ProjectApplication(
        id=str(uuid4()),
        project_id=str(uuid4()),
        freelancer_id=str(uuid4()),
        proposed_price=1500000,
        estimated_duration_days=14,
        proposal_message=(
            "Saya siap membuat website UMKM "
            "sesuai kebutuhan proyek."
        ),
    )


# TEST ENTITY
def test_application_default_status():
    application = make_application()

    assert application.status == "SUBMITTED"
    assert application.status == APPLICATION_SUBMITTED


def test_application_contains_required_fields():
    application = make_application()

    assert application.proposed_price == 1500000
    assert application.estimated_duration_days == 14
    assert "website UMKM" in application.proposal_message


def test_application_timestamps_are_optional():
    application = make_application()

    assert application.submitted_at is None
    assert application.created_at is None
    assert application.updated_at is None


def test_application_accepts_database_timestamps():
    now = datetime(2026, 11, 2, 10, 0)

    application = ProjectApplication(
        id=str(uuid4()),
        project_id=str(uuid4()),
        freelancer_id=str(uuid4()),
        proposed_price=250000,
        estimated_duration_days=3,
        proposal_message="Desain logo UMKM",
        submitted_at=now,
        created_at=now,
        updated_at=now,
    )

    assert application.submitted_at == now
    assert application.created_at == now
    assert application.updated_at == now


def test_application_is_immutable():
    application = make_application()

    with pytest.raises(FrozenInstanceError):
        application.status = "OTHER_STATUS"


# TEST REPOSITORY CONTRACT
@pytest.mark.parametrize(
    "method_name",
    [
        "freelancer_profile_exists",
        "project_is_open",
        "project_owned_by_umkm",
        "add",
        "get_by_id",
        "get_by_project_and_freelancer",
        "list_by_freelancer",
        "list_by_project",
    ],
)
def test_repository_contract_exists(method_name):
    assert callable(
        getattr(
            ApplicationRepository,
            method_name,
            None,
        )
    )