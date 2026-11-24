
from dataclasses import FrozenInstanceError

import pytest

from app.modules.matching.domain.entities import (
    FreelancerMatchingSource,
    FreelancerRecommendation,
    ProjectMatchingSource,
    ProjectRecommendation,
)

from app.modules.matching.domain.repositories import (
    MatchingRepository,
)

from app.modules.matching.domain.scoring import (
    calculate_skill_match,
)


# ============================================================
# PROJECT SOURCE TEST
# ============================================================

def test_project_source_fields():
    project = ProjectMatchingSource(
        project_id="p1",
        umkm_id="u1",
        title="Website UMKM",
        category_id="website",
        status="TERBUKA",
        required_skill_ids=(
            "python",
            "mysql",
        ),
    )

    assert project.umkm_id == "u1"
    assert project.required_skill_ids == (
        "python",
        "mysql",
    )


# ============================================================
# FREELANCER SOURCE TEST
# ============================================================

def test_freelancer_source_fields():
    freelancer = FreelancerMatchingSource(
        freelancer_id="f1",
        name="Andi",
        professional_title="Backend Developer",
        city="Malang",
        availability_status="AVAILABLE",
        skill_ids=("python",),
    )

    assert freelancer.service_price_min is None
    assert freelancer.skill_ids == ("python",)


# ============================================================
# BIDIRECTIONAL RECOMMENDATIONS
# ============================================================

def test_recommendations_work_in_both_directions():
    project = ProjectMatchingSource(
        project_id="p1",
        umkm_id="u1",
        title="Website",
        category_id="website",
        status="TERBUKA",
        required_skill_ids=("python",),
    )

    freelancer = FreelancerMatchingSource(
        freelancer_id="f1",
        name="Andi",
        professional_title="Developer",
        city="Malang",
        availability_status="AVAILABLE",
        skill_ids=("python",),
    )

    match = calculate_skill_match(
        project.required_skill_ids,
        freelancer.skill_ids,
    )

    freelancer_result = FreelancerRecommendation(
        freelancer=freelancer,
        match=match,
    )

    project_result = ProjectRecommendation(
        project=project,
        match=match,
    )

    assert (
        freelancer_result.match.score_percent
        == 100
    )

    assert project_result.project.project_id == "p1"


# ============================================================
# IMMUTABILITY
# ============================================================

def test_entities_are_immutable():
    project = ProjectMatchingSource(
        "p1",
        "u1",
        "Website",
        "website",
        "TERBUKA",
    )

    with pytest.raises(FrozenInstanceError):
        project.title = "Changed"


# ============================================================
# REPOSITORY CONTRACT
# ============================================================

@pytest.mark.parametrize(
    "method_name",
    [
        "get_project",
        "get_freelancer",
        "iter_available_freelancers",
        "iter_published_projects",
    ],
)
def test_matching_repository_contract_exists(
    method_name,
):
    assert callable(
        getattr(
            MatchingRepository,
            method_name,
            None,
        )
    )