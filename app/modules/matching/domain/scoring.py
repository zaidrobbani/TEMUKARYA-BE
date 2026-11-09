from collections.abc import Iterable

from app.modules.matching.domain.entities import (
    SkillMatchResult,
)


# ============================================================
# MATCHING BUSINESS RULE
# ============================================================

MIN_MATCH_SCORE = 60


# ============================================================
# NORMALIZE SKILL IDS
# ============================================================

def _unique_skill_ids(
    skill_ids: Iterable[str],
) -> tuple[str, ...]:
    """
    Membersihkan daftar skill ID.

    Aturan:
    1. Setiap ID harus string.
    2. Hapus spasi awal dan akhir.
    3. Tolak ID kosong.
    4. Hapus duplikasi.
    5. Pertahankan urutan pertama.
    """

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


# ============================================================
# CALCULATE SKILL MATCH
# ============================================================

def calculate_skill_match(
    required_skill_ids: Iterable[str],
    freelancer_skill_ids: Iterable[str],
) -> SkillMatchResult:
    """
    Menghitung skor kecocokan berdasarkan skill.

    Rumus:

    Matching Score (%) =
        (Matched Skills / Required Skills) * 100

    Threshold minimum: 60%.

    Project tanpa skill wajib menghasilkan
    skor 0 dan tidak lolos rekomendasi.

    Fungsi ini digunakan untuk:
    - Rekomendasi Freelancer kepada UMKM.
    - Rekomendasi Project kepada Freelancer.
    """

    # ========================================================
    # 1. NORMALIZE INPUT
    # ========================================================

    required = _unique_skill_ids(
        required_skill_ids
    )

    freelancer = set(
        _unique_skill_ids(
            freelancer_skill_ids
        )
    )

    # ========================================================
    # 2. IDENTIFY MATCHED SKILLS
    # ========================================================

    matched = tuple(
        skill
        for skill in required
        if skill in freelancer
    )

    # ========================================================
    # 3. IDENTIFY MISSING SKILLS
    # ========================================================

    missing = tuple(
        skill
        for skill in required
        if skill not in freelancer
    )

    # ========================================================
    # 4. COUNT SKILLS
    # ========================================================

    required_count = len(required)
    matched_count = len(matched)

    # ========================================================
    # 5. HANDLE EMPTY PROJECT REQUIREMENTS
    # ========================================================

    if required_count == 0:

        return SkillMatchResult(
            score_percent=0.0,
            required_count=0,
            matched_count=0,
            matched_skill_ids=(),
            missing_skill_ids=(),
            meets_threshold=False,
        )

    # ========================================================
    # 6. CALCULATE MATCHING SCORE
    # ========================================================

    score = round(
        matched_count * 100 / required_count,
        2,
    )

    # ========================================================
    # 7. CHECK MINIMUM THRESHOLD
    # ========================================================

    # Perbandingan bilangan bulat digunakan
    # agar keputusan threshold tidak dipengaruhi
    # pembulatan skor untuk tampilan.

    meets_threshold = (
        matched_count * 100
        >= MIN_MATCH_SCORE * required_count
    )

    # ========================================================
    # 8. RETURN MATCHING RESULT
    # ========================================================

    return SkillMatchResult(
        score_percent=score,
        required_count=required_count,
        matched_count=matched_count,
        matched_skill_ids=matched,
        missing_skill_ids=missing,
        meets_threshold=meets_threshold,
    )