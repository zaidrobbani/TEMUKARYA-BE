import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.core.config import API_PREFIX
from app.main import app
from app.modules.skills.application.use_cases import ListMasterData
from app.modules.skills.domain.entities import ProjectCategory, Skill
from app.modules.skills.presentation.dependencies import get_master_data_use_case


class FakeMasterDataRepository:
    def list_skills(self):
        return [Skill(id="logo_design", name="Desain Logo")]

    def list_categories(self):
        return [ProjectCategory(id="website", name="Website", description="Pembuatan website", is_active=True)]


@pytest.fixture
def client():
    app.dependency_overrides = {
        get_master_data_use_case: lambda: ListMasterData(FakeMasterDataRepository()),
    }
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


def test_every_api_route_uses_version_prefix():
    paths = [route.path for route in app.routes if isinstance(route, APIRoute)]

    assert paths
    assert all(path.startswith(f"{API_PREFIX}/") for path in paths)


@pytest.mark.parametrize("path", ["/health", "/skills", "/projects", "/auth/me", "/conversations"])
def test_unprefixed_paths_are_not_found(client, path):
    response = client.get(path)

    assert response.status_code == 404
    assert response.json() == {"success": False, "message": "Endpoint tidak ditemukan", "data": None}


def test_get_skills_uses_envelope(client):
    response = client.get(f"{API_PREFIX}/skills")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Daftar skill berhasil diambil",
        "data": [{"id": "logo_design", "name": "Desain Logo"}],
    }


def test_get_project_categories_uses_envelope(client):
    response = client.get(f"{API_PREFIX}/project-categories")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Daftar kategori project berhasil diambil",
        "data": [{"id": "website", "name": "Website", "description": "Pembuatan website", "is_active": True}],
    }


def test_skills_method_not_allowed(client):
    response = client.post(f"{API_PREFIX}/skills")

    assert response.status_code == 405
    assert response.json()["success"] is False
