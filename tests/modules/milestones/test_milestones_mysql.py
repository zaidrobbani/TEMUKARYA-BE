
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
)

from app.modules.milestones.application.dto import (
    GetDelayRiskInput,
    GetMilestonePlanInput,
    MilestoneActor,
)

from app.modules.milestones.application.use_cases import (
    GetMilestonePlan,
    GetMilestoneProgress,
    GetProjectDelayRisk,
    GetTotalMilestoneWeight,
)

from app.modules.milestones.domain.entities import (
    DelayRiskLevel,
    MilestoneStatus,
)

from app.modules.milestones.infrastructure.repositories import (
    SqlAlchemyMilestoneRepository,
)


# ============================================================
# 1. DATABASE SAFETY CHECK
# ============================================================

def verify_mysql_test_environment():

    if os.getenv("TEMUKARYA_RUN_MYSQL_TESTS") != "1":
        pytest.skip("MySQL integration test disabled")

    if engine.url.get_backend_name() != "mysql":
        pytest.fail("Database harus MySQL")

    if engine.url.host not in (
        "localhost",
        "127.0.0.1",
    ):
        pytest.fail(
            "Hanya MySQL lokal yang boleh diuji"
        )

    if engine.url.database != "temukarya":
        pytest.fail(
            "Nama database harus temukarya"
        )

    if settings.APP_ENV.lower() in (
        "production",
        "prod",
    ):
        pytest.fail(
            "Tidak boleh menguji database production"
        )


# ============================================================
# 2. INSERT HELPER
# ============================================================

def insert_data(
    session: Session,
    sql: str,
    params,
):
    session.execute(
        text(sql),
        params,
    )


# ============================================================
# 3. MYSQL INTEGRATION TEST
# ============================================================

def test_milestones_mysql_integration_and_rollback():

    verify_mysql_test_environment()

    # ========================================================
    # A. GENERATE UNIQUE TEST DATA
    # ========================================================

    tag = uuid4().hex[:12]

    owner_id = str(uuid4())
    project_id = str(uuid4())

    m1 = str(uuid4())
    m2 = str(uuid4())
    m3 = str(uuid4())

    category_id = f"ms-cat-{tag}"

    # ========================================================
    # B. START MYSQL TRANSACTION
    # ========================================================

    connection = engine.connect()
    transaction = connection.begin()

    try:

        with Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
        ) as session:

            # =================================================
            # 1. CREATE TEMPORARY UMKM USER
            # =================================================

            insert_data(
                session,
                """
                INSERT INTO users (
                    id,
                    name,
                    email,
                    password_hash,
                    role
                )
                VALUES (
                    :id,
                    :name,
                    :email,
                    :password_hash,
                    'umkm'
                )
                """,
                {
                    "id": owner_id,
                    "name": f"Milestone Test {tag}",
                    "email": (
                        f"milestone-{tag}@example.invalid"
                    ),
                    "password_hash": "test-only-hash",
                },
            )

            # =================================================
            # 2. CREATE UMKM PROFILE
            # =================================================

            insert_data(
                session,
                """
                INSERT INTO umkm_profiles (
                    user_id,
                    business_name,
                    business_category,
                    business_address,
                    city
                )
                VALUES (
                    :user_id,
                    :name,
                    'Technology',
                    'Test Address',
                    'Malang'
                )
                """,
                {
                    "user_id": owner_id,
                    "name": f"Milestone UMKM {tag}",
                },
            )

            # =================================================
            # 3. CREATE PROJECT CATEGORY
            # =================================================

            insert_data(
                session,
                """
                INSERT INTO project_categories (
                    id,
                    name,
                    description,
                    is_active
                )
                VALUES (
                    :id,
                    :name,
                    'Temporary test category',
                    1
                )
                """,
                {
                    "id": category_id,
                    "name": f"Milestone Category {tag}",
                },
            )

            # =================================================
            # 4. CREATE PROJECT
            # =================================================

            insert_data(
                session,
                """
                INSERT INTO projects (
                    id,
                    umkm_id,
                    category_id,
                    title,
                    description,
                    budget,
                    deadline,
                    status,
                    published_at,
                    started_at
                )
                VALUES (
                    :id,
                    :owner,
                    :category,
                    :title,
                    'Temporary milestone project',
                    2000000,
                    :deadline,
                    'TERBUKA',
                    :published,
                    :started
                )
                """,
                {
                    "id": project_id,
                    "owner": owner_id,
                    "category": category_id,
                    "title": f"Test Project {tag}",
                    "deadline": date(2026, 11, 11),
                    "published": datetime(2026, 11, 1, 8),
                    "started": datetime(2026, 11, 1, 8),
                },
            )

            # =================================================
            # 5. CREATE MILESTONES
            # =================================================

            insert_data(
                session,
                """
                INSERT INTO project_milestones (
                    id,
                    project_id,
                    name,
                    description,
                    weight_percent,
                    status,
                    sort_order,
                    completed_at,
                    updated_by_user_id
                )
                VALUES (
                    :id,
                    :project_id,
                    :name,
                    :description,
                    :weight,
                    :status,
                    :sort_order,
                    :completed_at,
                    :updated_by
                )
                """,
                [
                    {
                        "id": m1,
                        "project_id": project_id,
                        "name": "Planning",
                        "description": "Planning phase",
                        "weight": Decimal("20.00"),
                        "status": "SELESAI",
                        "sort_order": 1,
                        "completed_at": datetime(
                            2026, 11, 2, 8
                        ),
                        "updated_by": owner_id,
                    },
                    {
                        "id": m2,
                        "project_id": project_id,
                        "name": "Development",
                        "description": "Development phase",
                        "weight": Decimal("30.00"),
                        "status": "BELUM_SELESAI",
                        "sort_order": 2,
                        "completed_at": None,
                        "updated_by": None,
                    },
                    {
                        "id": m3,
                        "project_id": project_id,
                        "name": "Testing",
                        "description": "Testing phase",
                        "weight": Decimal("50.00"),
                        "status": "BELUM_SELESAI",
                        "sort_order": 3,
                        "completed_at": None,
                        "updated_by": None,
                    },
                ],
            )

            print("\nMYSQL TEST DATA CREATED: OK")

            # =================================================
            # 6. INITIALIZE REPOSITORY
            # =================================================

            repository = SqlAlchemyMilestoneRepository(
                session
            )

            actor = MilestoneActor(
                user_id=owner_id,
                role="umkm",
            )

            request = GetMilestonePlanInput(
                project_id=project_id,
                actor=actor,
            )

            # =================================================
            # 7. TEST MILESTONE PLAN
            # =================================================

            plan = GetMilestonePlan(
                repository
            ).execute(request)

            assert len(plan.items) == 3

            assert [
                item.id
                for item in plan.items
            ] == [m1, m2, m3]

            assert plan.total_weight == Decimal(
                "100.00"
            )

            assert plan.is_plan_complete is True

            print("MYSQL MILESTONE PLAN: OK")

            # =================================================
            # 8. TEST WORKFLOW WEIGHT CONTRACT
            # =================================================

            total = GetTotalMilestoneWeight(
                repository
            ).execute(project_id)

            assert total == Decimal("100.00")

            print("MYSQL TOTAL WEIGHT 100%: OK")

            # =================================================
            # 9. TEST WEIGHTED PROGRESS
            # =================================================

            progress = GetMilestoneProgress(
                repository
            ).execute(request)

            assert progress.total_weight == Decimal(
                "100.00"
            )

            assert progress.completed_weight == Decimal(
                "20.00"
            )

            assert progress.remaining_weight == Decimal(
                "80.00"
            )

            assert progress.progress_percent == Decimal(
                "20.00"
            )

            print("MYSQL WEIGHTED PROGRESS: OK")

            # =================================================
            # 10. TEST DELAY RISK
            # =================================================

            risk = GetProjectDelayRisk(
                repository
            ).execute(
                GetDelayRiskInput(
                    project_id=project_id,
                    actor=actor,
                    today=date(2026, 11, 6),
                )
            )

            assert risk.risk_level == (
                DelayRiskLevel.AT_RISK
            )

            assert risk.expected_progress_percent == (
                Decimal("50.00")
            )

            assert risk.actual_progress_percent == (
                Decimal("20.00")
            )

            print("MYSQL DELAY RISK: OK")

            # =================================================
            # 11. TEST OWNERSHIP PROTECTION
            # =================================================

            with pytest.raises(NotFoundError):

                GetMilestonePlan(
                    repository
                ).execute(
                    GetMilestonePlanInput(
                        project_id=project_id,
                        actor=MilestoneActor(
                            user_id=str(uuid4()),
                            role="umkm",
                        ),
                    )
                )

            print("MYSQL OWNERSHIP PROTECTION: OK")

            # =================================================
            # 12. TEST PLAN WRITE FAIL-CLOSED
            # =================================================

            with pytest.raises(ConflictError):

                repository.replace_plan_and_reset_approvals(
                    project_id,
                    (),
                )

            print("MYSQL PLAN WRITE FAIL-CLOSED: OK")

            # =================================================
            # 13. TEST CONDITIONAL COMPLETION
            # =================================================

            completed_at = datetime(
                2026,
                11,
                6,
                8,
                tzinfo=timezone.utc,
            )

            first = repository.complete_if_pending(
                project_id=project_id,
                milestone_id=m2,
                updated_by_user_id=owner_id,
                completed_at=completed_at,
            )

            second = repository.complete_if_pending(
                project_id=project_id,
                milestone_id=m2,
                updated_by_user_id=owner_id,
                completed_at=completed_at,
            )

            assert first is True
            assert second is False

            print("MYSQL IDEMPOTENT COMPLETION: OK")

            # =================================================
            # 14. VERIFY UPDATED PROGRESS
            # =================================================

            updated = repository.list_milestones(
                project_id
            )

            assert updated[1].status == (
                MilestoneStatus.SELESAI
            )

            assert updated[1].updated_by_user_id == (
                owner_id
            )

            assert updated[1].completed_at is not None

            progress_after = GetMilestoneProgress(
                repository
            ).execute(request)

            assert progress_after.progress_percent == (
                Decimal("50.00")
            )

            assert progress_after.completed_milestones == 2

            print("MYSQL UPDATED PROGRESS 50%: OK")

    finally:

        # ====================================================
        # 15. ALWAYS ROLLBACK
        # ====================================================

        if transaction.is_active:
            transaction.rollback()

        connection.close()

        print("MYSQL TRANSACTION ROLLBACK: OK")

    # ========================================================
    # 16. VERIFY NO TEST DATA LEFT
    # ========================================================

    checks = [
        ("users", "id", [owner_id]),
        ("umkm_profiles", "user_id", [owner_id]),
        ("project_categories", "id", [category_id]),
        ("projects", "id", [project_id]),
        ("project_milestones", "id", [m1, m2, m3]),
    ]

    with engine.connect() as check_connection:

        for table, column, ids in checks:

            statement = text(
                f"SELECT COUNT(*) FROM {table} "
                f"WHERE {column} IN :ids"
            ).bindparams(
                bindparam(
                    "ids",
                    expanding=True,
                )
            )

            remaining = check_connection.execute(
                statement,
                {"ids": ids},
            ).scalar_one()

            assert remaining == 0, (
                f"Temporary data remains in {table}"
            )

    print("MYSQL DATABASE CLEANUP: OK")
    print("MYSQL MILESTONES INTEGRATION: PASSED")