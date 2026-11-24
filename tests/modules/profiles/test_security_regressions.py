import ast
from collections import Counter
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import API_PREFIX
from app.core.exceptions import BadRequestError
from app.core.unit_of_work import UnitOfWork
from app.modules.profiles.application.dto import (
    CreateFreelancerExperienceInput, CreateFreelancerProfileInput,
    UpdateFreelancerExperienceInput,
)
from app.modules.profiles.application.use_cases import (
    CreateFreelancerExperience, CreateFreelancerProfile, UpdateFreelancerExperience,
)
from app.modules.profiles.domain.repositories import (
    FreelancerExperienceRepository, FreelancerProfileRepository,
)
from app.modules.profiles.presentation.auth import get_authenticated_profile_user
from app.modules.profiles.presentation.router import router


def execute_with_text(operation, value, profiles, experiences, uow):
    if operation == "profile":
        profiles.get_by_user_id.return_value = None
        profiles.add.side_effect = lambda profile: profile
        return CreateFreelancerProfile(profiles, uow).execute(
            "owner-1", CreateFreelancerProfileInput(
                professional_title="Designer", city="Malang", bio=value,
            ),
        )
    values = dict(
        job_title="Designer", organization_name="Studio", description=value,
        start_date=date(2024, 1, 1),
    )
    if operation == "create":
        return CreateFreelancerExperience(profiles, experiences, uow).execute(
            "owner-1", CreateFreelancerExperienceInput(**values),
        )
    experiences.update.return_value = True
    return UpdateFreelancerExperience(experiences, uow).execute(
        "owner-1", "experience-1", UpdateFreelancerExperienceInput(**values),
    )


@pytest.mark.parametrize("operation", ["profile", "create", "update"])
@pytest.mark.parametrize("value", ["a" * 65536, "\U0001f600" * 16384], ids=["ascii", "utf8"])
def test_text_exceeding_mysql_capacity_is_rejected_before_write(operation, value):
    profiles = MagicMock(spec=FreelancerProfileRepository)
    experiences = MagicMock(spec=FreelancerExperienceRepository)
    uow = MagicMock(spec=UnitOfWork)

    with pytest.raises(BadRequestError, match="65535 byte"):
        execute_with_text(operation, value, profiles, experiences, uow)

    profiles.add.assert_not_called()
    experiences.add.assert_not_called()
    experiences.update.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.parametrize("operation", ["profile", "create", "update"])
@pytest.mark.parametrize("value", ["a" * 65535, "\U0001f600" * 16383 + "abc"], ids=["ascii", "utf8"])
def test_text_at_mysql_capacity_is_accepted_after_trimming(operation, value):
    profiles = MagicMock(spec=FreelancerProfileRepository)
    experiences = MagicMock(spec=FreelancerExperienceRepository)
    uow = MagicMock(spec=UnitOfWork)

    result = execute_with_text(operation, "  " + value + "  ", profiles, experiences, uow)

    assert (result.bio if operation == "profile" else result.description) == value
    uow.commit.assert_called_once()


def test_profile_tests_have_no_shadowed_function_names():
    for path in Path(__file__).parent.glob("test_*.py"):
        names = [
            node.name for node in ast.parse(path.read_text(encoding="utf-8")).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ]
        assert len(names) == len(set(names)), f"Shadowed tests in {path.name}"


PROFILE_ROUTES = [
    (method, route.path)
    for route in router.routes for method in route.methods
]


@pytest.mark.parametrize("headers", [
    {}, {"Authorization": "Bearer forged-token", "X-User-Id": "owner-1", "X-Role": "FREELANCER"},
], ids=["anonymous", "forged-identity"])
@pytest.mark.parametrize("method,path", PROFILE_ROUTES)
def test_every_profile_route_is_registered_once_and_fail_closed(method, path, headers):
    from app.main import app

    registered = Counter(
        (method, route.path.removeprefix(API_PREFIX))
        for route in app.routes if route.path.startswith(f"{API_PREFIX}/profiles")
        for method in route.methods
    )
    assert registered == Counter(PROFILE_ROUTES)
    assert all(count == 1 for count in registered.values())
    assert app.dependency_overrides == {}
    full_path = f"{API_PREFIX}{path}"
    matching = next(route for route in app.routes if route.path == full_path and method in route.methods)
    assert any(dep.call is get_authenticated_profile_user for dep in matching.dependant.dependencies)

    with TestClient(app) as client:
        response = client.request(
            method,
            full_path.replace("{experience_id}", "foreign").replace("{portfolio_id}", "foreign").replace("{media_id}", "foreign"),
            headers=headers, params={"freelancer_id": "owner-2", "user_id": "owner-2"},
            json={"freelancer_id": "owner-2", "user_id": "owner-2"},
        )
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False and body["data"] is None
    if not headers:
        assert body["message"] == "Silakan login terlebih dahulu"
