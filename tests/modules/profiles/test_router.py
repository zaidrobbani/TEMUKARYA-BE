from datetime import date

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.error_handlers import register_error_handlers
from app.modules.users.domain.entities import UserRole

from app.modules.profiles.application.dto import CreateFreelancerExperienceInput

from app.modules.profiles.domain.entities import (
    UmkmProfile,
    FreelancerProfile,
    FreelancerExperience,
)

from app.modules.profiles.presentation.auth import (
    AuthenticatedProfileUser,
    get_authenticated_profile_user,
)

from app.modules.profiles.presentation.dependencies import (
    create_umkm_profile_use_case,
    create_freelancer_profile_use_case,
    create_freelancer_experience_use_case,
)

from app.modules.profiles.presentation.dependencies import (
    set_freelancer_skills_use_case,
)

from app.modules.profiles.presentation.dependencies import (
    get_freelancer_skills_use_case,
)

from app.modules.profiles.presentation.router import router


class FakeCreateUmkmProfile:
    def execute(self, user_id, data):
        return UmkmProfile(
            user_id=user_id,
            business_name=data.business_name,
            business_category=data.business_category,
            business_address=data.business_address,
            city=data.city,
        )


class FakeCreateFreelancerProfile:
    def execute(self, user_id, data):
        return FreelancerProfile(
            user_id=user_id,
            professional_title=data.professional_title,
            city=data.city,
            bio=data.bio,
            service_price_min=data.service_price_min,
            service_price_max=data.service_price_max,
            availability_status="AVAILABLE",
        )


class FakeCreateFreelancerExperience:
    def __init__(self):
        self.calls = []

    def execute(self, freelancer_id, data):
        self.calls.append((freelancer_id, data))
        return FreelancerExperience(
            id="experience-uuid-test",
            freelancer_id=freelancer_id,
            job_title=data.job_title,
            organization_name=data.organization_name,
            description=data.description,
            start_date=data.start_date,
            end_date=data.end_date,
        )


@pytest.fixture
def fake_create_freelancer_experience():
    return FakeCreateFreelancerExperience()


@pytest.fixture
def app(fake_create_freelancer_experience):
    test_app = FastAPI()

    register_error_handlers(test_app)
    test_app.include_router(router)

    test_app.dependency_overrides[
        create_umkm_profile_use_case
    ] = lambda: FakeCreateUmkmProfile()

    test_app.dependency_overrides[
        create_freelancer_profile_use_case
    ] = lambda: FakeCreateFreelancerProfile()

    test_app.dependency_overrides[
    set_freelancer_skills_use_case
    ] = lambda: FakeSetFreelancerSkills()

    test_app.dependency_overrides[
    get_freelancer_skills_use_case
    ] = lambda: FakeGetFreelancerSkills()

    test_app.dependency_overrides[
        create_freelancer_experience_use_case
    ] = lambda: fake_create_freelancer_experience

    return test_app


def umkm_payload():
    return {
        "business_name": "Kopi Malang",
        "business_category": "Food & Beverage",
        "business_address": "Jl. Soekarno Hatta",
        "city": "Malang",
    }


def freelancer_payload():
    return {
        "professional_title": "UI/UX Designer",
        "city": "Malang",
        "bio": "Desainer aplikasi mobile",
        "service_price_min": 150000,
        "service_price_max": 1000000,
    }


def login_as(app, role):
    app.dependency_overrides[
        get_authenticated_profile_user
    ] = lambda: AuthenticatedProfileUser(
        user_id="user-uuid-test",
        role=role,
    )


def test_create_umkm_returns_201(app):
    login_as(app, UserRole.UMKM)

    with TestClient(app) as client:
        response = client.post(
            "/profiles/umkm",
            json=umkm_payload(),
        )

    assert response.status_code == 201
    assert response.json()["data"]["business_name"] == "Kopi Malang"


def test_create_freelancer_returns_201(app):
    login_as(app, UserRole.FREELANCER)

    with TestClient(app) as client:
        response = client.post(
            "/profiles/freelancer",
            json=freelancer_payload(),
        )

    assert response.status_code == 201
    assert response.json()["data"]["professional_title"] == "UI/UX Designer"


def test_wrong_role_returns_403(app):
    login_as(app, UserRole.UMKM)

    with TestClient(app) as client:
        response = client.post(
            "/profiles/freelancer",
            json=freelancer_payload(),
        )

    assert response.status_code == 403


def test_unauthenticated_returns_401(app):
    with TestClient(app) as client:
        response = client.post(
            "/profiles/umkm",
            json=umkm_payload(),
        )

    assert response.status_code == 401


def test_invalid_payload_returns_422(app):
    login_as(app, UserRole.FREELANCER)

    with TestClient(app) as client:
        response = client.post(
            "/profiles/freelancer",
            json={"city": "Malang"},
        )

    assert response.status_code == 422


class FakeSetFreelancerSkills:
    def execute(self, freelancer_id, data):
        return data.skill_ids

    
class FakeGetFreelancerSkills:

    def execute(self, freelancer_id):
        return [
            "logo_design",
            "photo_editing",
        ]




# TEST 6: Freelancer berhasil mengubah keahlian
def test_update_freelancer_skills_explicit_payload_returns_200(app):
    login_as(app, UserRole.FREELANCER)

    with TestClient(app) as client:
        response = client.put(
            "/profiles/freelancer/skills",
            json={
                "skill_ids": [
                    "logo_design",
                    "web_programming",
                ]
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["skill_ids"] == [
        "logo_design",
        "web_programming",
    ]


# TEST 7: UMKM tidak boleh mengubah skill Freelancer
def test_update_skills_explicit_payload_wrong_role_returns_403(app):
    login_as(app, UserRole.UMKM)

    with TestClient(app) as client:
        response = client.put(
            "/profiles/freelancer/skills",
            json={
                "skill_ids": ["logo_design"]
            },
        )

    assert response.status_code == 403


# TEST 8: Pengguna tanpa login harus ditolak
def test_update_skills_explicit_payload_unauthenticated_returns_401(app):
    with TestClient(app) as client:
        response = client.put(
            "/profiles/freelancer/skills",
            json={
                "skill_ids": ["logo_design"]
            },
        )

    assert response.status_code == 401


# TEST 9: Format input yang salah harus ditolak
def test_update_skills_explicit_payload_invalid_returns_422(app):
    login_as(app, UserRole.FREELANCER)

    with TestClient(app) as client:
        response = client.put(
            "/profiles/freelancer/skills",
            json={
                "skill_ids": "logo_design"
            },
        )

    assert response.status_code == 422


def test_update_freelancer_skills_returns_200(app):
    login_as(app, UserRole.FREELANCER)

    with TestClient(app) as client:
        response = client.put(
            "/profiles/freelancer/skills",
            json={
                "skill_ids": [
                    "logo_design",
                    "web_programming"
                ]
            }
        )

    assert response.status_code == 200
    assert response.json()["data"]["skill_ids"] == [
        "logo_design",
        "web_programming"
    ]


def test_update_skills_wrong_role_returns_403(app):
    login_as(app, UserRole.UMKM)

    with TestClient(app) as client:
        response = client.put(
            "/profiles/freelancer/skills",
            json={"skill_ids": ["logo_design"]}
        )

    assert response.status_code == 403


def test_update_skills_unauthenticated_returns_401(app):
    with TestClient(app) as client:
        response = client.put(
            "/profiles/freelancer/skills",
            json={"skill_ids": ["logo_design"]}
        )

    assert response.status_code == 401


def test_update_skills_invalid_payload_returns_422(app):
    login_as(app, UserRole.FREELANCER)

    with TestClient(app) as client:
        response = client.put(
            "/profiles/freelancer/skills",
            json={"skill_ids": "logo_design"}
        )

    assert response.status_code == 422


# TEST 10: Freelancer berhasil melihat skill
def test_get_freelancer_skills_returns_200(app):
    login_as(app, UserRole.FREELANCER)

    with TestClient(app) as client:
        response = client.get(
            "/profiles/freelancer/skills"
        )

    assert response.status_code == 200
    assert response.json()["data"]["skill_ids"] == [
        "logo_design",
        "photo_editing",
    ]


# TEST 11: UMKM tidak boleh mengakses
def test_get_skills_wrong_role_returns_403(app):
    login_as(app, UserRole.UMKM)

    with TestClient(app) as client:
        response = client.get(
            "/profiles/freelancer/skills"
        )

    assert response.status_code == 403


# TEST 12: Pengguna belum login ditolak
def test_get_skills_unauthenticated_returns_401(app):
    with TestClient(app) as client:
        response = client.get(
            "/profiles/freelancer/skills"
        )

    assert response.status_code == 401


def freelancer_experience_payload():
    return {
        "job_title": "Graphic Designer",
        "organization_name": "Studio Kreatif ABC",
        "description": "Membuat desain branding UMKM",
        "start_date": "2024-01-15",
        "end_date": "2025-12-20",
    }


def test_create_freelancer_experience_returns_201(
    app, fake_create_freelancer_experience
):
    login_as(app, UserRole.FREELANCER)

    with TestClient(app) as client:
        response = client.post(
            "/profiles/freelancer/experiences",
            json=freelancer_experience_payload(),
        )

    assert response.status_code == 201
    assert response.json()["data"] == {
        "id": "experience-uuid-test",
        "freelancer_id": "user-uuid-test",
        **freelancer_experience_payload(),
    }
    assert fake_create_freelancer_experience.calls == [
        (
            "user-uuid-test",
            CreateFreelancerExperienceInput(
                job_title="Graphic Designer",
                organization_name="Studio Kreatif ABC",
                description="Membuat desain branding UMKM",
                start_date=date(2024, 1, 15),
                end_date=date(2025, 12, 20),
            ),
        )
    ]


def test_create_experience_wrong_role_returns_403(
    app, fake_create_freelancer_experience
):
    login_as(app, UserRole.UMKM)

    with TestClient(app) as client:
        response = client.post(
            "/profiles/freelancer/experiences",
            json=freelancer_experience_payload(),
        )

    assert response.status_code == 403
    assert response.json() == {"success": False, "message": "Hanya Freelancer yang dapat menambahkan pengalaman kerja", "data": None}
    assert fake_create_freelancer_experience.calls == []


def test_create_experience_unauthenticated_returns_401(
    app, fake_create_freelancer_experience
):
    with TestClient(app) as client:
        response = client.post(
            "/profiles/freelancer/experiences",
            json=freelancer_experience_payload(),
        )

    assert response.status_code == 401
    assert response.json() == {"success": False, "message": "Silakan login terlebih dahulu", "data": None}
    assert fake_create_freelancer_experience.calls == []


def test_create_experience_invalid_payload_returns_422(
    app, fake_create_freelancer_experience
):
    login_as(app, UserRole.FREELANCER)
    payload = freelancer_experience_payload()
    payload["job_title"] = ""

    with TestClient(app) as client:
        response = client.post(
            "/profiles/freelancer/experiences",
            json=payload,
        )

    assert response.status_code == 422
    assert {"field": "job_title", "message": "Wajib diisi"} in response.json()["errors"]
    assert fake_create_freelancer_experience.calls == []
