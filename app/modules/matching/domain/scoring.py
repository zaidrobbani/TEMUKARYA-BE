from collections.abc import Iterable

from app.modules.matching.domain.entities import (
    SkillMatchResult,
)


MIN_MATCH_SCORE = 60


def _unique_skill_ids(
    skill_ids: Iterable[str],
) -> tuple[str, ...]:
    if skill_ids is None or isinstance(
        skill_ids,
        (str, bytes),
    ):
        raise TypeError(
            "skill_ids harus berupa kumpulan ID skill"
        )

    seen: set[str] = set()
    unique: list[str] = []

    for skill_id in skill_ids:
        if not isinstance(skill_id, str):
            raise TypeError(
                "setiap skill_id harus berupa string"
            )

        normalized = skill_id.strip()

        if not normalized:
            raise ValueError(
                "skill_id tidak boleh kosong"
            )

        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)

    return tuple(unique)


def calculate_skill_match(
    required_skill_ids: Iterable[str],
    freelancer_skill_ids: Iterable[str],
) -> SkillMatchResult:
    required = _unique_skill_ids(
        required_skill_ids
    )

    freelancer = set(
        _unique_skill_ids(
            freelancer_skill_ids
        )
    )

    matched = tuple(
        skill
        for skill in required
        if skill in freelancer
    )

    missing = tuple(
        skill
        for skill in required
        if skill not in freelancer
    )

    required_count = len(required)
    matched_count = len(matched)

    if required_count == 0:
        return SkillMatchResult(
            score_percent=0.0,
            required_count=0,
            matched_count=0,
            matched_skill_ids=(),
            missing_skill_ids=(),
            meets_threshold=False,
        )

    score = round(
        matched_count * 100 / required_count,
        2,
    )

    meets_threshold = (
        matched_count * 100
        >= MIN_MATCH_SCORE * required_count
    )

    return SkillMatchResult(
        score_percent=score,
        required_count=required_count,
        matched_count=matched_count,
        matched_skill_ids=matched,
        missing_skill_ids=missing,
        meets_threshold=meets_threshold,
    )
