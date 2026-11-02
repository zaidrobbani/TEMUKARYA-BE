from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError

from app.modules.milestones.infrastructure.models import (
    ProjectMilestoneModel,
)

from app.modules.milestones.infrastructure.repositories import (
    SqlAlchemyMilestoneRepository,
)

# SQLITE TEST DATABASE

@pytest.fixture
def repo():

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    # ========================================================
    # 1. CREATE TEST TABLES
    # ========================================================

    with engine.begin() as connection:

        connection.execute(
            text("""
                CREATE TABLE projects (
                    id TEXT PRIMARY KEY,
                    umkm_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    deadline TEXT NOT NULL
                )
            """)
        )

        connection.execute(
            text("""
                CREATE TABLE users (
                    id TEXT PRIMARY KEY
                )
            """)
        )

        connection.execute(
            text("""
                CREATE TABLE project_milestones (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    weight_percent NUMERIC(5,2) NOT NULL,
                    status TEXT NOT NULL
                        DEFAULT 'BELUM_SELESAI',
                    sort_order INTEGER NOT NULL,
                    completed_at TEXT,
                    updated_by_user_id TEXT,
                    created_at TEXT,
                    updated_at TEXT,

                    UNIQUE (project_id, sort_order),

                    CHECK (
                        weight_percent > 0
                        AND weight_percent <= 100
                    )
                )
            """)
        )

        # ====================================================
        # 2. SEED PROJECT AND USER
        # ====================================================

        connection.execute(
            text("""
                INSERT INTO projects
                VALUES (
                    'p1',
                    'u1',
                    'SEDANG_DIKERJAKAN',
                    '2026-11-01 00:00:00',
                    '2026-11-11'
                )
            """)
        )

        connection.execute(
            text("""
                INSERT INTO users
                VALUES ('u1')
            """)
        )

        # ====================================================
        # 3. SEED MILESTONES
        # ====================================================

        connection.execute(
            text("""
                INSERT INTO project_milestones (
                    id,
                    project_id,
                    name,
                    description,
                    weight_percent,
                    status,
                    sort_order
                )
                VALUES
                (
                    'm1', 'p1', 'Design',
                    'Design task', 33.33,
                    'BELUM_SELESAI', 1
                ),
                (
                    'm2', 'p1', 'Code',
                    'Code task', 33.33,
                    'SELESAI', 2
                ),
                (
                    'm3', 'p1', 'Test',
                    'QA', 33.34,
                    'BELUM_SELESAI', 3
                )
            """)
        )

    # ========================================================
    # 4. PROVIDE REPOSITORY
    # ========================================================

    try:
        with Session(engine) as session:

            repository = (
                SqlAlchemyMilestoneRepository(
                    session
                )
            )

            yield repository, session

    finally:
        engine.dispose()


# ============================================================
# TEST 1 - GET PROJECT CONTEXT
# ============================================================

def test_context(repo):
    repository, _ = repo

    project = repository.get_project_context(
        "p1"
    )

    assert project.umkm_id == "u1"
    assert project.project_id == "p1"

    # Freelancer access belum terintegrasi.
    assert project.freelancer_id is None

    assert project.deadline == date(
        2026, 11, 11
    )


# ============================================================
# TEST 2 - PROJECT NOT FOUND
# ============================================================

def test_missing_context(repo):
    repository, _ = repo

    assert repository.get_project_context(
        "missing"
    ) is None


# ============================================================
# TEST 3 - LIST MILESTONES
# ============================================================

def test_list(repo):
    repository, _ = repo

    items = repository.list_milestones(
        "p1"
    )

    assert [
        item.id
        for item in items
    ] == [
        "m1",
        "m2",
        "m3",
    ]

    assert items[0].weight_percent == Decimal(
        "33.33"
    )

    assert items[1].status == "SELESAI"


# ============================================================
# TEST 4 - EXACT TOTAL WEIGHT
# ============================================================

def test_total(repo):
    repository, _ = repo

    assert repository.get_total_weight(
        "p1"
    ) == Decimal("100.00")

    assert repository.get_total_weight(
        "missing"
    ) == Decimal("0.00")


# ============================================================
# TEST 5 - PLAN REPLACEMENT FAIL-CLOSED
# ============================================================

def test_fails_closed_write_plan(repo):
    repository, session = repo

    with pytest.raises(ConflictError):
        repository.replace_plan_and_reset_approvals(
            "p1",
            (),
        )

    count = session.execute(
        text(
            "SELECT COUNT(*) "
            "FROM project_milestones"
        )
    ).scalar_one()

    assert count == 3


# ============================================================
# TEST 6 - CONDITIONAL COMPLETION
# ============================================================

def test_completion_atomic(repo):
    repository, session = repo

    completed_at = datetime(
        2026,
        11,
        2,
        15,
        0,
        tzinfo=timezone.utc,
    )

    first = repository.complete_if_pending(
        project_id="p1",
        milestone_id="m1",
        updated_by_user_id="u1",
        completed_at=completed_at,
    )

    second = repository.complete_if_pending(
        project_id="p1",
        milestone_id="m1",
        updated_by_user_id="u1",
        completed_at=completed_at,
    )

    assert first is True
    assert second is False

    status = session.execute(
        text("""
            SELECT status
            FROM project_milestones
            WHERE id = 'm1'
        """)
    ).scalar_one()

    assert status == "SELESAI"

    stored_time = session.execute(
        text("""
            SELECT completed_at
            FROM project_milestones
            WHERE id = 'm1'
        """)
    ).scalar_one()

    assert str(stored_time).startswith(
        "2026-11-02"
    )


# ============================================================
# TEST 7 - WRONG PROJECT OR MILESTONE
# ============================================================

def test_wrong_project_or_id(repo):
    repository, _ = repo

    now = datetime.now(
        timezone.utc
    )

    assert repository.complete_if_pending(
        "wrong",
        "m3",
        "u1",
        now,
    ) is False

    assert repository.complete_if_pending(
        "p1",
        "wrong",
        "u1",
        now,
    ) is False


# ============================================================
# TEST 8 - READ ONLY QUERIES
# ============================================================

def test_read_only_methods(repo):
    repository, session = repo

    before = session.execute(
        text(
            "SELECT COUNT(*) "
            "FROM project_milestones"
        )
    ).scalar_one()

    repository.get_project_context("p1")
    repository.list_milestones("p1")
    repository.get_total_weight("p1")

    after = session.execute(
        text(
            "SELECT COUNT(*) "
            "FROM project_milestones"
        )
    ).scalar_one()

    assert before == after


# ============================================================
# TEST 9 - ORM MODEL METADATA
# ============================================================

def test_model_metadata():
    table = ProjectMilestoneModel.__table__

    assert str(
        table.c.weight_percent.type
    ) == "NUMERIC(5, 2)"

    assert table.c.project_id.foreign_keys

    assert (
        table.c.updated_by_user_id.foreign_keys
    )