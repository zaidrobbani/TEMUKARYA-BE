
import pytest

from app.modules.matching.domain.scoring import (
    MIN_MATCH_SCORE,
    calculate_skill_match,
)


# ============================================================
# THRESHOLD
# ============================================================

def test_threshold_is_60_percent():
    assert MIN_MATCH_SCORE == 60


# ============================================================
# MATCHING SCORE CALCULATION
# ============================================================

@pytest.mark.parametrize(
    "owned,expected_score,eligible",
    [
        ((), 0.0, False),
        (
            ("python", "fastapi"),
            40.0,
            False,
        ),
        (
            ("python", "fastapi", "mysql"),
            60.0,
            True,
        ),
        (
            ("python", "fastapi", "mysql", "docker"),
            80.0,
            True,
        ),
        (
            (
                "python",
                "fastapi",
                "mysql",
                "docker",
                "react",
            ),
            100.0,
            True,
        ),
    ],
)
def test_matching_score_and_threshold(
    owned,
    expected_score,
    eligible,
):
    result = calculate_skill_match(
        (
            "python",
            "fastapi",
            "mysql",
            "docker",
            "react",
        ),
        owned,
    )

    assert result.score_percent == expected_score
    assert result.meets_threshold is eligible


# ============================================================
# MATCHED AND MISSING SKILLS
# ============================================================

def test_explainable_matched_and_missing_skills():
    result = calculate_skill_match(
        ("python", "fastapi", "mysql"),
        ("mysql", "python", "kotlin"),
    )

    assert result.score_percent == 66.67
    assert result.required_count == 3
    assert result.matched_count == 2

    assert result.matched_skill_ids == (
        "python",
        "mysql",
    )

    assert result.missing_skill_ids == (
        "fastapi",
    )


# ============================================================
# DUPLICATE SKILLS
# ============================================================

def test_duplicate_skills_are_not_double_counted():
    result = calculate_skill_match(
        ("python", "python", "mysql"),
        ("python", "python", "docker"),
    )

    assert result.required_count == 2
    assert result.matched_count == 1
    assert result.score_percent == 50.0
    assert not result.meets_threshold


# ============================================================
# EMPTY PROJECT REQUIREMENTS
# ============================================================

def test_empty_project_requirements_do_not_match():
    result = calculate_skill_match(
        (),
        ("python",),
    )

    assert result.score_percent == 0.0
    assert result.required_count == 0
    assert result.matched_skill_ids == ()
    assert result.missing_skill_ids == ()
    assert not result.meets_threshold


# ============================================================
# EXTRA FREELANCER SKILLS
# ============================================================

def test_extra_freelancer_skills_do_not_increase_score():
    result = calculate_skill_match(
        ("python",),
        ("python", "docker", "java"),
    )

    assert result.score_percent == 100.0
    assert result.matched_count == 1


# ============================================================
# SKILL ID NORMALIZATION
# ============================================================

def test_skill_ids_are_trimmed_but_not_case_folded():
    result = calculate_skill_match(
        (" python ", "mysql"),
        ("python", "MySQL"),
    )

    assert result.score_percent == 50.0

    assert result.missing_skill_ids == (
        "mysql",
    )


# ============================================================
# INVALID SKILL COLLECTIONS
# ============================================================

@pytest.mark.parametrize(
    "bad_skills",
    [
        None,
        "python",
        (123,),
        ("",),
        ("   ",),
    ],
)
def test_invalid_skill_collections_rejected(
    bad_skills,
):
    with pytest.raises(
        (TypeError, ValueError)
    ):
        calculate_skill_match(
            bad_skills,
            ("python",),
        )


# ============================================================
# INVALID FREELANCER SKILLS
# ============================================================

def test_invalid_freelancer_skill_ids_rejected():
    with pytest.raises(TypeError):
        calculate_skill_match(
            ("python",),
            (None,),
        )