from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import get_uow
from app.core.error_handlers import register_error_handlers
from app.modules.profiles.presentation.auth import AuthenticatedProfileUser, get_authenticated_profile_user
from app.modules.profiles.presentation.dependencies import get_freelancer_profile_repository, get_umkm_profile_repository
from app.modules.profiles.presentation.router import router
from app.modules.users.domain.entities import UserRole


PAYLOADS = {
    "umkm": dict(business_name="Kopi", business_category="Food", business_address="Jl. A", city="Malang"),
    "freelancer": dict(professional_title="Designer", city="Malang", availability_status="AVAILABLE"),
}
ROLES = {"umkm": UserRole.UMKM, "freelancer": UserRole.FREELANCER}


@pytest.fixture(params=["umkm", "freelancer"])
def self_profile_api(request, self_profile_store):
    kind = request.param
    repositories, session, uow = self_profile_store
    repository = MagicMock(wraps=repositories[kind])
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    dependency = get_umkm_profile_repository if kind == "umkm" else get_freelancer_profile_repository
    app.dependency_overrides[dependency] = lambda: repository
    app.dependency_overrides[get_uow] = lambda: uow
    app.dependency_overrides[get_authenticated_profile_user] = lambda: AuthenticatedProfileUser("owner-1", ROLES[kind])
    with TestClient(app) as client:
        yield kind, app, client, repository, uow


def test_self_profile_http_get_put_ignore_forged_query_and_headers(self_profile_api):
    kind, app, client, repository, uow = self_profile_api
    path = f"/profiles/{kind}/me"
    foreign = repository.get_by_user_id("owner-2")
    query = {"user_id": "owner-2", "freelancer_id": "owner-2", "id": "owner-2", "role": "ADMIN"}
    headers = {"X-User-Id": "owner-2", "X-Role": "ADMIN"}
    response = client.get(path, params=query, headers=headers)
    assert response.status_code == 200 and response.json()["user_id"] == "owner-1"
    uow.commit.assert_not_called()
    updated = client.put(path, json={**PAYLOADS[kind], "city": " Surabaya "}, params=query, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["user_id"] == "owner-1" and updated.json()["city"] == "Surabaya"
    if kind == "freelancer":
        assert all(updated.json()[field] is None for field in ("bio", "service_price_min", "service_price_max"))
    assert client.get(path).json() == updated.json()
    assert repository.get_by_user_id("owner-2") == foreign
    assert "created_at" not in updated.json() and "updated_at" not in updated.json()
    uow.commit.assert_called_once_with()


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_self_profile_http_role_mismatch_rejected_without_repository_access(self_profile_api, method):
    kind, app, client, repository, uow = self_profile_api
    other_role = UserRole.FREELANCER if kind == "umkm" else UserRole.UMKM
    app.dependency_overrides[get_authenticated_profile_user] = lambda: AuthenticatedProfileUser("owner-1", other_role)
    response = client.request(method, f"/profiles/{kind}/me", json=PAYLOADS[kind])
    assert response.status_code == 403
    repository.get_by_user_id.assert_not_called()
    repository.update.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_self_profile_http_missing_profile_does_not_fall_back_to_query_owner(self_profile_api, method):
    kind, app, client, repository, uow = self_profile_api
    app.dependency_overrides[get_authenticated_profile_user] = lambda: AuthenticatedProfileUser("missing", ROLES[kind])
    response = client.request(method, f"/profiles/{kind}/me", json=PAYLOADS[kind], params={"user_id": "owner-2"})
    assert response.status_code == 404
    repository.get_by_user_id.assert_called_once_with("missing")
    repository.update.assert_not_called()
    repository.add.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.parametrize("field", ["user_id", "freelancer_id", "owner_id", "id", "role", "created_at", "updated_at"])
def test_self_profile_http_rejects_identity_and_audit_fields(self_profile_api, field):
    kind, app, client, repository, uow = self_profile_api
    response = client.put(f"/profiles/{kind}/me", json={**PAYLOADS[kind], field: "owner-2"})
    assert response.status_code == 422
    repository.update.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.parametrize("case", ["missing", "null", "empty", "length", "blank"])
def test_self_profile_http_validates_all_required_fields(self_profile_api, case):
    kind, app, client, repository, uow = self_profile_api
    limits = {"city": 100, "business_name": 160, "business_category": 100,
              "business_address": 300, "professional_title": 150, "availability_status": 25}
    for field in PAYLOADS[kind]:
        body = PAYLOADS[kind].copy()
        if case == "missing":
            body.pop(field)
        else:
            body[field] = {"null": None, "empty": "", "length": "a" * (limits[field] + 1), "blank": " "}[case]
        response = client.put(f"/profiles/{kind}/me", json=body)
        assert response.status_code == (400 if case == "blank" else 422), (field, response.text)
    repository.update.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.parametrize("body,expected", [
    ({"bio": "\U0001f600" * 16384}, 400),
    ({"service_price_min": 2, "service_price_max": 1}, 400),
    ({"service_price_min": -1}, 422), ({"service_price_max": -1}, 422),
    ({"service_price_min": 2**64}, 422), ({"service_price_max": 2**64}, 422),
    ({"service_price_min": True}, 422), ({"service_price_max": 1.2}, 422),
    ({"service_price_min": "100"}, 422),
])
def test_freelancer_http_bio_and_price_validation(self_profile_store, body, expected):
    repositories, _, uow = self_profile_store
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    repository = MagicMock(wraps=repositories["freelancer"])
    app.dependency_overrides[get_freelancer_profile_repository] = lambda: repository
    app.dependency_overrides[get_uow] = lambda: uow
    app.dependency_overrides[get_authenticated_profile_user] = lambda: AuthenticatedProfileUser("owner-1", UserRole.FREELANCER)
    with TestClient(app) as client:
        response = client.put("/profiles/freelancer/me", json={**PAYLOADS["freelancer"], **body})
    assert response.status_code == expected
    repository.update.assert_not_called()
    uow.commit.assert_not_called()


def test_freelancer_http_explicit_optional_values_and_null(self_profile_store):
    repositories, _, uow = self_profile_store
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_freelancer_profile_repository] = lambda: repositories["freelancer"]
    app.dependency_overrides[get_uow] = lambda: uow
    app.dependency_overrides[get_authenticated_profile_user] = lambda: AuthenticatedProfileUser("owner-1", UserRole.FREELANCER)
    with TestClient(app) as client:
        for values in (
            dict(bio=" New bio ", service_price_min=0, service_price_max=250000),
            dict(bio=None, service_price_min=None, service_price_max=None),
        ):
            response = client.put("/profiles/freelancer/me", json={**PAYLOADS["freelancer"], **values})
            assert response.status_code == 200
            assert response.json()["bio"] == (values["bio"].strip() if values["bio"] else None)
            assert response.json()["service_price_min"] == values["service_price_min"]
            assert response.json()["service_price_max"] == values["service_price_max"]
