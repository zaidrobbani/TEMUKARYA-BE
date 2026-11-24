from dataclasses import (
    FrozenInstanceError,
    asdict,
)
from datetime import date, datetime, timezone

import pytest

from app.modules.admin_statistics.domain.entities import (
    AdminActor,
    AdminUserSummary,
    AdminUMKMProfile,
    AdminFreelancerProfile,
    AdminUserDetail,
    AdminProjectSummary,
    AdminProjectDetail,
    AdminSystemStatistics,
)


# ============================================================
# 1. TEST CONSTANTS
# ============================================================

NOW = datetime(
    2026, 11, 4, 10, 0,
    tzinfo=timezone.utc,
)

DEADLINE = date(2026, 12, 1)


# ============================================================
# 2. TEST DATA HELPERS
# ============================================================

def make_user(
    role: str = "umkm",
) -> AdminUserSummary:
    return AdminUserSummary(
        id="user-001",
        name="Test User",
        email="user@example.com",
        role=role,
        created_at=NOW,
    )


def make_umkm_profile() -> AdminUMKMProfile:
    return AdminUMKMProfile(
        business_name="UMKM Digital",
        business_category="Technology",
        business_address="Malang",
        city="Malang",
    )


def make_freelancer_profile() -> AdminFreelancerProfile:
    return AdminFreelancerProfile(
        professional_title="UI/UX Designer",
        bio="Freelance designer",
        city="Malang",
        service_price_min=100000,
        service_price_max=1000000,
        availability_status="AVAILABLE",
    )


def make_project(
    assigned: bool = False,
) -> AdminProjectSummary:
    return AdminProjectSummary(
        id="project-001",
        title="Website UMKM",
        category_id="web-development",
        umkm_id="umkm-001",
        umkm_name="UMKM Digital",
        assigned_freelancer_id=(
            "freelancer-001" if assigned else None
        ),
        assigned_freelancer_name=(
            "Freelancer Test" if assigned else None
        ),
        budget=2000000,
        deadline=DEADLINE,
        status="TERBUKA",
        created_at=NOW,
    )


# ============================================================
# 3. ADMIN ACTOR
# ============================================================

def test_admin_actor_creation():
    actor = AdminActor(
        user_id="admin-001",
        role="admin",
    )

    assert actor.user_id == "admin-001"
    assert actor.role == "admin"


def test_admin_actor_is_immutable():
    actor = AdminActor(
        user_id="admin-001",
        role="admin",
    )

    with pytest.raises(FrozenInstanceError):
        actor.role = "umkm"


# ============================================================
# 4. USER SUMMARY
# ============================================================

def test_user_summary_creation():
    user = make_user()

    assert user.id == "user-001"
    assert user.name == "Test User"
    assert user.email == "user@example.com"
    assert user.role == "umkm"
    assert user.created_at == NOW


def test_user_summary_excludes_password():
    user = make_user()

    data = asdict(user)

    assert "password_hash" not in data
    assert "password" not in data


def test_user_summary_is_immutable():
    user = make_user()

    with pytest.raises(FrozenInstanceError):
        user.email = "changed@example.com"


# ============================================================
# 5. UMKM PROFILE
# ============================================================

def test_umkm_profile_creation():
    profile = make_umkm_profile()

    assert profile.business_name == "UMKM Digital"
    assert profile.business_category == "Technology"
    assert profile.business_address == "Malang"
    assert profile.city == "Malang"


def test_umkm_profile_is_immutable():
    profile = make_umkm_profile()

    with pytest.raises(FrozenInstanceError):
        profile.city = "Jakarta"


# ============================================================
# 6. FREELANCER PROFILE
# ============================================================

def test_freelancer_profile_creation():
    profile = make_freelancer_profile()

    assert profile.professional_title == "UI/UX Designer"
    assert profile.bio == "Freelance designer"
    assert profile.city == "Malang"
    assert profile.service_price_min == 100000
    assert profile.service_price_max == 1000000
    assert profile.availability_status == "AVAILABLE"


def test_freelancer_profile_nullable_fields():
    profile = AdminFreelancerProfile(
        professional_title="Developer",
        bio=None,
        city="Malang",
        service_price_min=None,
        service_price_max=None,
        availability_status="AVAILABLE",
    )

    assert profile.bio is None
    assert profile.service_price_min is None
    assert profile.service_price_max is None


# ============================================================
# 7. USER DETAIL
# ============================================================

def test_umkm_user_detail():
    detail = AdminUserDetail(
        user=make_user("umkm"),
        umkm_profile=make_umkm_profile(),
    )

    assert detail.user.role == "umkm"
    assert detail.umkm_profile is not None
    assert detail.freelancer_profile is None


def test_freelancer_user_detail():
    detail = AdminUserDetail(
        user=make_user("freelancer"),
        freelancer_profile=make_freelancer_profile(),
    )

    assert detail.user.role == "freelancer"
    assert detail.freelancer_profile is not None
    assert detail.umkm_profile is None


def test_user_detail_without_profile():
    detail = AdminUserDetail(
        user=make_user(),
    )

    assert detail.umkm_profile is None
    assert detail.freelancer_profile is None


def test_user_detail_excludes_password():
    detail = AdminUserDetail(
        user=make_user(),
        umkm_profile=make_umkm_profile(),
    )

    data = asdict(detail)

    assert "password_hash" not in data["user"]
    assert "password" not in data["user"]


# ============================================================
# 8. PROJECT SUMMARY
# ============================================================

def test_project_without_freelancer():
    project = make_project(
        assigned=False,
    )

    assert project.id == "project-001"
    assert project.budget == 2000000
    assert project.status == "TERBUKA"

    assert project.assigned_freelancer_id is None
    assert project.assigned_freelancer_name is None


def test_project_with_freelancer():
    project = make_project(
        assigned=True,
    )

    assert project.assigned_freelancer_id == (
        "freelancer-001"
    )

    assert project.assigned_freelancer_name == (
        "Freelancer Test"
    )


def test_project_summary_is_immutable():
    project = make_project()

    with pytest.raises(FrozenInstanceError):
        project.budget = 0


# ============================================================
# 9. PROJECT DETAIL
# ============================================================

def test_project_detail_with_agreement():
    detail = AdminProjectDetail(
        project=make_project(assigned=True),
        description="Membuat website UMKM",
        agreed_price=1800000,
        published_at=NOW,
        started_at=NOW,
        completed_at=None,
    )

    assert detail.project.id == "project-001"
    assert detail.agreed_price == 1800000
    assert detail.started_at == NOW
    assert detail.completed_at is None


def test_project_detail_without_agreement():
    detail = AdminProjectDetail(
        project=make_project(),
        description="Project belum ditugaskan",
        agreed_price=None,
        published_at=None,
        started_at=None,
        completed_at=None,
    )

    assert detail.agreed_price is None
    assert detail.project.assigned_freelancer_id is None


# ============================================================
# 10. SYSTEM STATISTICS
# ============================================================

def test_system_statistics_creation():
    stats = AdminSystemStatistics(
        total_umkm=10,
        total_freelancers=20,
        total_projects=15,
        completed_projects=5,
        total_transactions=7,
        platform_income=350000,
    )

    assert stats.total_umkm == 10
    assert stats.total_freelancers == 20
    assert stats.total_projects == 15
    assert stats.completed_projects == 5
    assert stats.total_transactions == 7
    assert stats.platform_income == 350000


def test_system_statistics_zero_values():
    stats = AdminSystemStatistics(
        total_umkm=0,
        total_freelancers=0,
        total_projects=0,
        completed_projects=0,
        total_transactions=0,
        platform_income=0,
    )

    assert stats.total_projects == 0
    assert stats.platform_income == 0


def test_system_statistics_is_immutable():
    stats = AdminSystemStatistics(
        total_umkm=1,
        total_freelancers=1,
        total_projects=1,
        completed_projects=0,
        total_transactions=0,
        platform_income=0,
    )

    with pytest.raises(FrozenInstanceError):
        stats.total_projects = 999