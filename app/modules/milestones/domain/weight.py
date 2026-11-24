
from collections.abc import Iterable
from decimal import Decimal

from app.modules.milestones.domain.entities import (
    Milestone,
)


# ============================================================
# WEIGHT CONSTANTS
# ============================================================

ZERO = Decimal("0.00")
HUNDRED = Decimal("100.00")
PRECISION = Decimal("0.01")


# ============================================================
# 1. VALIDATE INDIVIDUAL WEIGHT
# ============================================================

def validate_weight(
    value: Decimal,
) -> Decimal:
    """
    Validasi satu bobot milestone.

    Aturan:
    - Harus Decimal
    - Tidak boleh NaN / Infinity
    - Harus lebih dari 0
    - Maksimum 100
    - Maksimal dua angka desimal
    """

    if not isinstance(value, Decimal):
        raise TypeError(
            "Bobot milestone harus menggunakan Decimal"
        )

    if not value.is_finite():
        raise ValueError(
            "Bobot milestone harus berupa angka valid"
        )

    if value <= ZERO or value > HUNDRED:
        raise ValueError(
            "Bobot milestone harus lebih dari 0 "
            "dan maksimal 100"
        )

    normalized = value.quantize(PRECISION)

    if value != normalized:
        raise ValueError(
            "Bobot milestone maksimal dua angka desimal"
        )

    return normalized


# ============================================================
# 2. CALCULATE TOTAL WEIGHT
# ============================================================

def calculate_total_weight(
    milestones: Iterable[Milestone],
) -> Decimal:
    """
    Menjumlahkan bobot seluruh milestone.

    Ini fungsi Domain murni.

    Kontrak get_total_weight(project_id)
    untuk Workflow akan dibuat pada Repository.
    """

    return sum(
        (
            validate_weight(item.weight_percent)
            for item in milestones
        ),
        ZERO,
    )


# ============================================================
# 3. VALIDATE MILESTONE PLAN
# ============================================================

def validate_milestone_plan(
    milestones: Iterable[Milestone],
) -> Decimal:
    """
    Memvalidasi kumpulan milestone:

    - Berasal dari project yang sama
    - Nama tidak kosong
    - Sort order unik
    - Bobot individual valid
    - Total tidak melebihi 100%

    Rencana dengan total kurang dari 100%
    masih dianggap draft, bukan final.
    """

    items = tuple(milestones)

    project_ids: set[str] = set()
    sort_orders: set[int] = set()

    for item in items:

        if not item.project_id.strip():
            raise ValueError(
                "Project ID tidak boleh kosong"
            )

        project_ids.add(item.project_id)

        if not item.name.strip():
            raise ValueError(
                "Nama milestone tidak boleh kosong"
            )

        if len(item.name) > 180:
            raise ValueError(
                "Nama milestone maksimal 180 karakter"
            )

        if (
            type(item.sort_order) is not int
            or item.sort_order < 1
        ):
            raise ValueError(
                "Sort order harus bilangan bulat positif"
            )

        if item.sort_order in sort_orders:
            raise ValueError(
                "Sort order milestone tidak boleh duplikat"
            )

        sort_orders.add(item.sort_order)

        validate_weight(item.weight_percent)

    if len(project_ids) > 1:
        raise ValueError(
            "Semua milestone harus berasal "
            "dari project yang sama"
        )

    total = calculate_total_weight(items)

    if total > HUNDRED:
        raise ValueError(
            "Total bobot milestone tidak boleh "
            "melebihi 100%"
        )

    return total


# ============================================================
# 4. REQUIRE FINALIZED PLAN
# ============================================================

def require_complete_plan(
    milestones: Iterable[Milestone],
) -> Decimal:
    """
    Memastikan total bobot tepat 100%.

    Digunakan sebagai dasar validasi
    sebelum Workflow mengizinkan 'Lanjut'.
    """

    total = validate_milestone_plan(milestones)

    if total != HUNDRED:
        raise ValueError(
            "Total bobot milestone harus tepat 100%"
        )

    return total