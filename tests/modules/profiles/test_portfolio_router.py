from datetime import datetime
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import get_uow
from app.core.error_handlers import register_error_handlers
from app.modules.profiles.domain.repositories import FreelancerProfileRepository
from app.modules.profiles.presentation.auth import AuthenticatedProfileUser, get_authenticated_profile_user
from app.modules.profiles.presentation.dependencies import get_portfolio_repository, get_freelancer_profile_repository
from app.modules.profiles.presentation.dependencies import get_media_repository, get_portfolio_storage
from app.modules.profiles.infrastructure.media_repository import SqlAlchemyMediaRepository
from app.modules.profiles.infrastructure.media_storage import LocalImageStorage
from app.modules.profiles.presentation.router import router
from app.modules.users.domain.entities import UserRole


BASE = "/profiles/freelancer/portfolios"
OPERATIONS = [("POST", ""), ("GET", ""), ("GET", "/own-a"), ("PUT", "/own-a"), ("DELETE", "/own-a")]


def payload():
    return {"title": "Branding", "description": "Desain untuk UMKM", "project_url": "https://example.com/work"}


@pytest.fixture
def portfolio_app(portfolio_store, portfolio_session, tmp_path):
    repository, uow = portfolio_store
    repository = MagicMock(wraps=repository)
    profiles = MagicMock(spec=FreelancerProfileRepository)
    test_app = FastAPI()
    register_error_handlers(test_app)
    test_app.include_router(router)
    test_app.dependency_overrides[get_portfolio_repository] = lambda: repository
    test_app.dependency_overrides[get_freelancer_profile_repository] = lambda: profiles
    test_app.dependency_overrides[get_uow] = lambda: uow
    test_app.dependency_overrides[get_media_repository] = lambda: SqlAlchemyMediaRepository(portfolio_session)
    test_app.dependency_overrides[get_portfolio_storage] = lambda: LocalImageStorage(tmp_path)
    return test_app, repository, profiles, uow


def login_as(app, role=UserRole.FREELANCER, user_id="owner-1"):
    app.dependency_overrides[get_authenticated_profile_user] = lambda: AuthenticatedProfileUser(user_id=user_id, role=role)


def test_create_and_get_portfolio_metadata(portfolio_app):
    app, repository, profiles, uow = portfolio_app
    login_as(app)
    with TestClient(app) as client:
        response = client.post(BASE, json=payload(), params={"freelancer_id": "owner-2"})
        assert response.status_code == 201
        assert response.json()["message"] == "Portfolio berhasil dibuat"
        saved = response.json()["data"]
        detail = client.get(BASE + "/" + saved["id"], params={"freelancer_id": "owner-2"})
    UUID(saved["id"])
    assert {key: saved[key] for key in payload()} == payload()
    assert saved["freelancer_id"] == "owner-1"
    assert saved["created_at"].endswith("Z")
    assert datetime.fromisoformat(saved["created_at"]) == datetime.fromisoformat(saved["updated_at"])
    assert detail.status_code == 200 and detail.json()["data"] == saved
    profiles.get_by_user_id.assert_called_once_with("owner-1")
    repository.add.assert_called_once()
    uow.commit.assert_called_once()


@pytest.mark.parametrize("url_mode", ["omitted", "null", "url"])
def test_update_portfolio_replaces_metadata_and_preserves_owner_and_creation_time(portfolio_app, url_mode):
    app, repository, _, uow = portfolio_app
    login_as(app)
    before = repository.get_by_id("own-a", "owner-1")
    body = {**payload(), "title": "  Updated  ", "description": "  Description  "}
    if url_mode == "omitted":
        body.pop("project_url")
    elif url_mode == "null":
        body["project_url"] = None
    with TestClient(app) as client:
        response = client.put(BASE + "/own-a", json=body, params={"freelancer_id": "owner-2"})
        detail = client.get(BASE + "/own-a")
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Updated"
    assert response.json()["data"]["description"] == "Description"
    assert response.json()["data"]["freelancer_id"] == "owner-1"
    assert response.json()["data"]["project_url"] == body.get("project_url")
    created_at = datetime.fromisoformat(response.json()["data"]["created_at"])
    assert created_at.replace(tzinfo=None) == before.created_at.replace(
        microsecond=before.created_at.microsecond // 1000 * 1000
    )
    assert detail.json()["data"] == response.json()["data"]
    assert repository.get_by_id("foreign", "owner-2").title == "foreign"
    uow.commit.assert_called_once()


def test_delete_portfolio_returns_200_and_then_404(portfolio_app):
    app, repository, _, uow = portfolio_app
    login_as(app)
    with TestClient(app) as client:
        response = client.delete(BASE + "/own-a", params={"freelancer_id": "owner-2"})
        detail = client.get(BASE + "/own-a")
        repeated = client.delete(BASE + "/own-a")
    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Portfolio berhasil dihapus", "data": None}
    assert detail.status_code == repeated.status_code == 404
    assert repository.get_by_id("own-b", "owner-1") is not None
    assert repository.get_by_id("foreign", "owner-2") is not None
    uow.commit.assert_called_once()


def test_list_portfolios_returns_private_pages(portfolio_app):
    app, repository, _, uow = portfolio_app
    login_as(app)
    with TestClient(app) as client:
        first = client.get(BASE, params={"limit": 2, "freelancer_id": "owner-2"})
        second = client.get(BASE, params={"limit": 2, "offset": 2})
        empty = client.get(BASE, params={"offset": 3})
        maximum = client.get(BASE, params={"limit": 100, "offset": 10000})
    assert first.status_code == second.status_code == empty.status_code == maximum.status_code == 200
    assert [item["id"] for item in first.json()["data"]["items"]] == ["own-a", "own-b"]
    assert (first.json()["data"]["limit"], first.json()["data"]["offset"], first.json()["data"]["has_more"]) == (2, 0, True)
    assert [item["id"] for item in second.json()["data"]["items"]] == ["own-old"]
    assert second.json()["data"]["has_more"] is False
    assert empty.json()["data"] == {"items": [], "limit": 20, "offset": 3, "has_more": False}
    assert maximum.json()["data"] == {"items": [], "limit": 100, "offset": 10000, "has_more": False}
    repository.list_by_freelancer_id.assert_any_call("owner-1", 3, 0)
    uow.commit.assert_not_called()


def test_list_portfolios_empty_owner(portfolio_app):
    app, _, _, _ = portfolio_app
    login_as(app, user_id="empty")
    with TestClient(app) as client:
        response = client.get(BASE)
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Daftar portfolio berhasil diambil",
        "data": {"items": [], "limit": 20, "offset": 0, "has_more": False},
    }


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": -1}, {"limit": 101}, {"limit": "invalid"},
    {"offset": -1}, {"offset": 10001}, {"offset": "1.5"},
])
def test_portfolio_pagination_rejects_invalid_requests(portfolio_app, params):
    app, repository, _, _ = portfolio_app
    login_as(app)
    with TestClient(app) as client:
        response = client.get(BASE, params=params)
    assert response.status_code == 422
    repository.list_by_freelancer_id.assert_not_called()


@pytest.mark.parametrize("method,suffix", OPERATIONS)
@pytest.mark.parametrize("role,status", [(UserRole.UMKM, 403), (None, 401)])
def test_portfolio_requires_authenticated_freelancer(portfolio_app, method, suffix, role, status):
    app, repository, profiles, uow = portfolio_app
    if role is not None:
        login_as(app, role=role)
    with TestClient(app) as client:
        response = client.request(method, BASE + suffix, json=payload() if method in {"POST", "PUT"} else None)
    assert response.status_code == status
    assert repository.mock_calls == []
    assert profiles.mock_calls == []
    uow.commit.assert_not_called()


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
@pytest.mark.parametrize("target", ["foreign", "missing"])
def test_portfolio_foreign_or_missing_id_is_404_even_with_forged_owner(portfolio_app, method, target):
    app, repository, _, uow = portfolio_app
    login_as(app)
    before = repository.get_by_id("foreign", "owner-2")
    own_before = repository.get_by_id("own-a", "owner-1")
    with TestClient(app) as client:
        response = client.request(
            method, BASE + "/" + target, params={"freelancer_id": "owner-2", "user_id": "owner-2"},
            json=payload() if method == "PUT" else {"freelancer_id": "owner-2"},
        )
    assert response.status_code == 404
    assert response.json() == {"success": False, "message": "Portfolio tidak ditemukan", "data": None}
    assert repository.get_by_id("foreign", "owner-2") == before
    assert repository.get_by_id("own-a", "owner-1") == own_before
    uow.commit.assert_not_called()


@pytest.mark.parametrize("method,suffix", [("POST", ""), ("PUT", "/own-a")])
@pytest.mark.parametrize("changes,status", [
    pytest.param({"title": ""}, 422, id="empty-title"),
    pytest.param({"title": "a" * 181}, 422, id="long-title"),
    pytest.param({"title": "   "}, 400, id="blank-title"),
    pytest.param({"description": ""}, 422, id="empty-description"),
    pytest.param({"description": "  "}, 400, id="blank-description"),
    pytest.param({"description": "a" * 65536}, 400, id="oversize-ascii"),
    pytest.param({"description": "\U0001f600" * 16384}, 400, id="oversize-utf8"),
    pytest.param({"project_url": "javascript:alert(1)"}, 400, id="unsafe-scheme"),
    pytest.param({"project_url": "https://user:pass@example.com"}, 400, id="credentials"),
    pytest.param({"project_url": "https://"}, 400, id="missing-host"),
    pytest.param({"project_url": "a" * 1001}, 422, id="long-url"),
    pytest.param({"freelancer_id": "owner-2"}, 422, id="forged-owner"),
    pytest.param({"id": "foreign"}, 422, id="forged-id"),
    pytest.param({"created_at": "2000-01-01"}, 422, id="forged-created"),
    pytest.param({"updated_at": "2000-01-01"}, 422, id="forged-updated"),
])
def test_portfolio_metadata_validation_and_mass_assignment_protection(portfolio_app, method, suffix, changes, status):
    app, repository, _, uow = portfolio_app
    login_as(app)
    with TestClient(app) as client:
        response = client.request(method, BASE + suffix, json={**payload(), **changes})
    assert response.status_code == status
    repository.add.assert_not_called()
    repository.update.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.parametrize("method,suffix", [("POST", ""), ("PUT", "/own-a")])
def test_portfolio_requires_complete_metadata(portfolio_app, method, suffix):
    app, repository, _, uow = portfolio_app
    login_as(app)
    with TestClient(app) as client:
        response = client.request(method, BASE + suffix, json={"title": "Only title"})
    assert response.status_code == 422
    repository.add.assert_not_called()
    repository.update.assert_not_called()
    uow.commit.assert_not_called()


def test_create_portfolio_without_freelancer_profile_returns_404(portfolio_app):
    app, repository, profiles, uow = portfolio_app
    profiles.get_by_user_id.return_value = None
    login_as(app)
    with TestClient(app) as client:
        response = client.post(BASE, json=payload())
    assert response.status_code == 404
    assert response.json() == {"success": False, "message": "Profil Freelancer tidak ditemukan", "data": None}
    repository.add.assert_not_called()
    uow.commit.assert_not_called()
