from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import API_PREFIX
from app.core.dependencies import get_uow
from app.core.error_handlers import register_error_handlers
from app.modules.profiles.presentation.auth import (
    AuthenticatedProfileUser, get_authenticated_profile_user,
)
from app.modules.profiles.presentation.dependencies import (
    get_freelancer_experience_repository,
)
from app.modules.profiles.presentation.router import router
from app.modules.users.domain.entities import UserRole


BASE_URL = "/profiles/freelancer/experiences"
OPERATIONS = [("GET", ""), ("PUT", "/own-newer"), ("DELETE", "/own-newer")]


def payload():
    return {
        "job_title": "Senior Designer",
        "organization_name": "Studio Baru",
        "description": "Membuat desain aplikasi",
        "start_date": "2024-02-01",
        "end_date": "2025-02-01",
    }


def login_as(app, role=UserRole.FREELANCER, user_id="owner-1"):
    app.dependency_overrides[get_authenticated_profile_user] = lambda: (
        AuthenticatedProfileUser(user_id=user_id, role=role)
    )


@pytest.fixture
def experience_app(experience_store):
    repository, uow = experience_store
    # Exercise the real dependency factories, use cases and SQL queries.
    # All overrides belong to this test application, never app.main.app.
    repository_spy = MagicMock(wraps=repository)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_freelancer_experience_repository] = lambda: repository_spy
    app.dependency_overrides[get_uow] = lambda: uow
    return app, repository_spy, uow


def test_get_experiences_returns_only_logged_in_owner(experience_app):
    app, repository, _ = experience_app
    login_as(app)
    with TestClient(app) as client:
        response = client.get(BASE_URL, params={"freelancer_id": "owner-2"})

    assert response.status_code == 200
    assert response.json()["message"] == "Daftar pengalaman kerja berhasil diambil"
    assert [item["id"] for item in response.json()["data"]] == ["own-newer", "own-older"]
    assert all(item["freelancer_id"] == "owner-1" for item in response.json()["data"])
    assert response.json()["data"][0] == {
        "id": "own-newer", "freelancer_id": "owner-1",
        "job_title": "Designer", "organization_name": "Studio",
        "description": "Branding", "start_date": "2024-01-01", "end_date": None,
    }
    repository.list_by_freelancer_id.assert_called_once_with("owner-1")


def test_get_experiences_returns_empty_list(experience_app):
    app, _, _ = experience_app
    login_as(app, user_id="empty-owner")
    with TestClient(app) as client:
        response = client.get(BASE_URL)
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.parametrize("end_date", ["2025-02-01", None, "omitted"])
def test_update_experience_returns_200_and_persists(experience_app, end_date):
    app, repository, uow = experience_app
    login_as(app)
    body = payload()
    if end_date == "omitted":
        body.pop("end_date")
    else:
        body["end_date"] = end_date
    body["job_title"] = "  Senior Designer  "
    with TestClient(app) as client:
        response = client.put(BASE_URL + "/own-newer", json=body)
        listed = client.get(BASE_URL)

    assert response.status_code == 200
    assert response.json()["data"] == {
        **body, "job_title": "Senior Designer", "end_date": body.get("end_date"),
        "id": "own-newer", "freelancer_id": "owner-1",
    }
    assert listed.json()["data"][0] == response.json()["data"]
    repository.update.assert_called_once()
    uow.commit.assert_called_once()


def test_delete_experience_returns_200_with_empty_data(experience_app):
    app, repository, uow = experience_app
    login_as(app)
    with TestClient(app) as client:
        response = client.delete(BASE_URL + "/own-newer")
        listed = client.get(BASE_URL)
        repeated = client.delete(BASE_URL + "/own-newer")

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Pengalaman kerja berhasil dihapus", "data": None}
    assert [item["id"] for item in listed.json()["data"]] == ["own-older"]
    assert repeated.status_code == 404
    repository.delete.assert_any_call("own-newer", "owner-1")
    uow.commit.assert_called_once()


@pytest.mark.parametrize("method,suffix", OPERATIONS)
@pytest.mark.parametrize("role,status", [(UserRole.UMKM, 403), (None, 401)])
def test_experiences_reject_unauthorized_access(experience_app, method, suffix, role, status):
    app, repository, uow = experience_app
    if role is not None:
        login_as(app, role=role)
    with TestClient(app) as client:
        response = client.request(
            method, BASE_URL + suffix, **({"json": payload()} if method == "PUT" else {}),
        )

    assert response.status_code == status
    repository.list_by_freelancer_id.assert_not_called()
    repository.update.assert_not_called()
    repository.delete.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
@pytest.mark.parametrize("target_id", ["foreign", "missing"])
def test_experiences_hide_missing_and_foreign_ids(experience_app, method, target_id):
    app, repository, uow = experience_app
    login_as(app)
    foreign_before = repository.list_by_freelancer_id("owner-2")
    own_before = repository.list_by_freelancer_id("owner-1")
    with TestClient(app) as client:
        response = client.request(
            method, BASE_URL + "/" + target_id,
            params={"freelancer_id": "owner-2", "user_id": "owner-2"},
            json=payload() if method == "PUT" else {"freelancer_id": "owner-2"},
        )

    assert response.status_code == 404
    assert response.json() == {"success": False, "message": "Pengalaman kerja tidak ditemukan", "data": None}
    assert repository.list_by_freelancer_id("owner-2") == foreign_before
    assert repository.list_by_freelancer_id("owner-1") == own_before
    uow.commit.assert_not_called()


@pytest.mark.parametrize("changes,status,field", [
    ({"job_title": ""}, 422, "job_title"),
    ({"job_title": "A" * 151}, 422, "job_title"),
    ({"organization_name": ""}, 422, "organization_name"),
    ({"organization_name": "A" * 161}, 422, "organization_name"),
    ({"description": ""}, 422, "description"),
    ({"start_date": "not-a-date"}, 422, "start_date"),
    ({"end_date": "not-a-date"}, 422, "end_date"),
    ({"start_date": None}, 422, "start_date"),
    ({"job_title": "   "}, 400, None),
    ({"organization_name": "   "}, 400, None),
    ({"description": "   "}, 400, None),
    ({"description": "a" * 65536}, 400, None),
    ({"description": "\U0001f600" * 16384}, 400, None),
    ({"end_date": "2023-01-01"}, 400, None),
    ({"freelancer_id": "owner-2"}, 422, "freelancer_id"),
    ({"id": "foreign"}, 422, "id"),
])
def test_update_experience_rejects_invalid_input(experience_app, changes, status, field):
    app, repository, uow = experience_app
    login_as(app)
    with TestClient(app) as client:
        response = client.put(BASE_URL + "/own-newer", json={**payload(), **changes})

    assert response.status_code == status
    if field is not None:
        assert any(error["field"] == field for error in response.json()["errors"])
    repository.update.assert_not_called()
    uow.commit.assert_not_called()


def test_put_requires_complete_payload(experience_app):
    app, repository, uow = experience_app
    login_as(app)
    with TestClient(app) as client:
        response = client.put(BASE_URL + "/own-newer", json={"job_title": "Designer"})
    assert response.status_code == 422
    assert {(error["field"], error["message"]) for error in response.json()["errors"]} == {
        ("organization_name", "Wajib diisi"), ("description", "Wajib diisi"), ("start_date", "Wajib diisi"),
    }
    repository.update.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.parametrize("method,suffix", OPERATIONS)
def test_real_application_registers_routes_and_remains_fail_closed(method, suffix):
    from app.main import app

    assert get_authenticated_profile_user not in app.dependency_overrides
    routes = [
        route for route in app.routes
        if getattr(route, "path", None) == API_PREFIX + (
            BASE_URL if method == "GET" else BASE_URL + "/{experience_id}"
        ) and method in getattr(route, "methods", set())
    ]
    assert len(routes) == 1
    with TestClient(app) as client:
        response = client.request(
            method, API_PREFIX + BASE_URL + suffix, **({"json": payload()} if method == "PUT" else {}),
        )
    assert response.status_code == 401
    assert response.json() == {"success": False, "message": "Silakan login terlebih dahulu", "data": None}
