from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import get_uow
from app.core.error_handlers import register_error_handlers
from app.core.unit_of_work import UnitOfWork
from app.modules.profiles.infrastructure.media_repository import SqlAlchemyMediaRepository
from app.modules.profiles.infrastructure.media_storage import LocalImageStorage
from app.modules.profiles.presentation.auth import AuthenticatedProfileUser, get_authenticated_profile_user
from app.modules.profiles.presentation.dependencies import get_media_repository, get_portfolio_storage
from app.modules.profiles.presentation.router import router
from app.modules.users.domain.entities import UserRole
from tests.modules.profiles.test_media_storage import image_bytes

BASE = "/profiles/freelancer/portfolios/own-a/media"


@pytest.fixture
def media_client(portfolio_session, tmp_path):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    storage = LocalImageStorage(tmp_path)
    repository = SqlAlchemyMediaRepository(portfolio_session)
    uow = MagicMock(spec=UnitOfWork)
    uow.commit.side_effect = portfolio_session.commit
    app.dependency_overrides[get_media_repository] = lambda: repository
    app.dependency_overrides[get_portfolio_storage] = lambda: storage
    app.dependency_overrides[get_uow] = lambda: uow
    app.dependency_overrides[get_authenticated_profile_user] = lambda: AuthenticatedProfileUser("owner-1", UserRole.FREELANCER)
    with TestClient(app) as client:
        yield client, app, storage, repository


def post(client, path=BASE, data=None, filename="../../fake.jpg", mime="application/pdf"):
    return client.post(path, files={"file": (filename, image_bytes() if data is None else data, mime)})


def test_http_upload_list_authorized_file_cover_order_and_delete(media_client):
    client, _, storage, _ = media_client
    first = post(client)
    assert first.status_code == 201
    assert first.json()["message"] == "Media portfolio berhasil diunggah"
    first = first.json()["data"]
    assert first["is_cover"] is True and first["mime_type"] == "image/png"
    assert "storage_key" not in first
    second = post(client).json()["data"]
    assert second["is_cover"] is False
    listed = client.get(BASE)
    assert listed.status_code == 200 and len(listed.json()["data"]) == 2
    file = client.get(f"{BASE}/{first['id']}/file")
    assert file.status_code == 200 and file.content.startswith(b"\x89PNG")
    assert len(file.content) == first["file_size_bytes"]
    assert file.headers["cache-control"] == "private, no-store"
    assert file.headers["x-content-type-options"] == "nosniff"
    assert client.patch(f"{BASE}/{second['id']}/cover").status_code == 200
    ordered = client.patch(BASE + "/order", json={"media_ids": [second["id"], first["id"]]})
    assert ordered.status_code == 200 and ordered.json()["data"][0]["is_cover"] is True
    deleted = client.delete(f"{BASE}/{second['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"success": True, "message": "Media portfolio berhasil dihapus", "data": None}
    assert client.get(BASE).json()["data"][0]["is_cover"] is True
    assert client.delete("/profiles/freelancer/portfolios/own-a").status_code == 200
    assert not list(storage.root.iterdir())


@pytest.mark.parametrize("data,status", [
    (b"", 422), (b"<svg/>", 415), (b"%PDF", 415),
    (b"\xff\xd8broken", 422), (b"x" * (5 * 1024 * 1024 + 1), 413),
])
def test_invalid_upload_status_and_cleanup(media_client, data, status):
    client, _, storage, repository = media_client
    response = post(client, data=data)
    assert response.status_code == status
    assert response.json()["success"] is False and response.json()["data"] is None
    assert isinstance(response.json()["message"], str)
    assert repository.list("own-a") == []
    assert not list(storage.root.iterdir())


def test_http_limit_and_invalid_order(media_client):
    client, _, storage, _ = media_client
    for _ in range(5):
        assert post(client).status_code == 201
    assert post(client).status_code == 409
    assert len(list(storage.root.iterdir())) == 5
    assert client.patch(BASE + "/order", json={"media_ids": []}).status_code == 422
    assert client.patch(BASE + "/order", json={"media_ids": ["foreign"]}).status_code == 422
    assert client.patch(BASE + "/order", json={"media_ids": [], "freelancer_id": "owner-2"}).status_code == 422


@pytest.mark.parametrize("method,suffix", [
    ("POST", ""), ("GET", ""), ("GET", "/x/file"),
    ("PATCH", "/x/cover"), ("PATCH", "/order"), ("DELETE", "/x"),
])
@pytest.mark.parametrize("role,status", [(None, 401), (UserRole.UMKM, 403)])
def test_media_auth_and_roles(media_client, method, suffix, role, status):
    client, app, storage, _ = media_client
    if role is None:
        app.dependency_overrides.pop(get_authenticated_profile_user)
    else:
        app.dependency_overrides[get_authenticated_profile_user] = lambda: AuthenticatedProfileUser("owner-1", role)
    if method == "POST":
        response = post(client)
    else:
        response = client.request(method, BASE + suffix, json={"media_ids": []})
    assert response.status_code == status
    assert not list(storage.root.iterdir())


def test_other_owner_cannot_access_any_media_operation(media_client):
    client, app, storage, repository = media_client
    item = post(client).json()["data"]
    app.dependency_overrides[get_authenticated_profile_user] = lambda: AuthenticatedProfileUser("owner-2", UserRole.FREELANCER)
    for method, suffix, body in [
        ("GET", "", None), ("GET", f"/{item['id']}/file", None),
        ("PATCH", f"/{item['id']}/cover", None), ("DELETE", f"/{item['id']}", None),
        ("PATCH", "/order", {"media_ids": [item["id"]]}),
    ]:
        response = client.request(method, BASE + suffix, json=body, params={"freelancer_id": "owner-1"})
        assert response.status_code == 404
    assert post(client).status_code == 404
    assert len(repository.list("own-a")) == len(list(storage.root.iterdir())) == 1


def test_media_id_must_belong_to_path_portfolio(media_client):
    client, _, _, _ = media_client
    item = post(client, BASE.replace("own-a", "own-b")).json()["data"]
    assert client.get(f"{BASE}/{item['id']}/file").status_code == 404
    assert client.patch(f"{BASE}/{item['id']}/cover").status_code == 404
    assert client.delete(f"{BASE}/{item['id']}").status_code == 404


def test_missing_file_and_failed_cleanup_are_visible(media_client, monkeypatch):
    client, _, storage, repository = media_client
    item = post(client).json()["data"]
    row = repository.list("own-a")[0]
    (storage.root / row.storage_key).unlink()
    assert client.get(f"{BASE}/{item['id']}/file").status_code == 503
    from app.modules.profiles.domain.media import StorageFailure
    def fail(key):
        raise StorageFailure("permission denied")
    monkeypatch.setattr(storage, "delete", fail)
    failed = client.delete(f"{BASE}/{item['id']}")
    assert failed.status_code == 503
    assert failed.json()["success"] is False
    assert repository.list("own-a") == []


def test_client_metadata_and_extra_file_parts_are_rejected(media_client):
    client, _, storage, _ = media_client
    response = client.post(BASE, files={"file": ("a.png", image_bytes(), "image/png")}, data={"storage_key": "../secret"})
    assert response.status_code == 422
    response = client.post(BASE, files=[("file", ("a.png", image_bytes())), ("file", ("b.png", image_bytes()))])
    assert response.status_code == 422
    assert not list(storage.root.iterdir())


def test_storage_is_not_publicly_mounted():
    from app.main import app
    with TestClient(app) as client:
        assert client.get("/storage/portfolios/example.png").status_code == 404
        assert client.get("/api/v1/storage/portfolios/example.png").status_code == 404
