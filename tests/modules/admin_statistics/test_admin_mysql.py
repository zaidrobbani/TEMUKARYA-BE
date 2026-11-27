import os
from dataclasses import asdict

import pytest

from sqlalchemy import (
    event,
    inspect,
    text,
)
from sqlalchemy.orm import Session

from app.core.database import engine

from app.modules.admin_statistics.infrastructure.repositories import (
    SqlAlchemyAdminStatisticsRepository,
)


REQUIRED_COLUMNS = {
    "users": {
        "id",
        "name",
        "email",
        "role",
        "created_at",
    },
    "umkm_profiles": {
        "user_id",
        "business_name",
        "business_category",
        "business_address",
        "city",
    },
    "freelancer_profiles": {
        "user_id",
        "professional_title",
        "bio",
        "city",
        "service_price_min",
        "service_price_max",
        "availability_status",
    },
    "projects": {
        "id",
        "title",
        "category_id",
        "umkm_id",
        "budget",
        "deadline",
        "status",
        "created_at",
        "description",
        "published_at",
        "started_at",
        "completed_at",
    },
    "project_agreements": {
        "project_id",
        "freelancer_id",
        "agreed_price",
    },
    "payments": {
        "id",
        "status",
        "platform_fee_amount",
    },
}


def require_safe_mysql() -> None:
    if os.getenv(
        "TEMUKARYA_RUN_MYSQL_TESTS"
    ) != "1":
        pytest.skip(
            "MySQL integration test belum diaktifkan"
        )

    if engine.dialect.name != "mysql":
        pytest.fail(
            "Admin integration test membutuhkan MySQL"
        )

    if engine.url.host not in {
        "localhost",
        "127.0.0.1",
    }:
        pytest.fail(
            "Hanya MySQL lokal yang diizinkan"
        )

    if engine.url.database != "temukarya":
        pytest.fail(
            "Database harus bernama temukarya"
        )

    from app.core.config import settings

    app_env = str(
        getattr(settings, "APP_ENV", "development")
    ).lower()

    if app_env in {
        "prod",
        "production",
    }:
        pytest.fail(
            "Dilarang menjalankan test "
            "pada environment production"
        )

    inspector = inspect(engine)

    existing_tables = set(
        inspector.get_table_names()
    )

    for table, required in REQUIRED_COLUMNS.items():
        if table not in existing_tables:
            pytest.fail(
                f"Required table belum ada: {table}"
            )

        actual_columns = {
            column["name"]
            for column in inspector.get_columns(table)
        }

        missing = required - actual_columns

        if missing:
            pytest.fail(
                f"Kolom {table} belum lengkap: "
                + ", ".join(sorted(missing))
            )

    print("\nMYSQL ADMIN SCHEMA AUDIT: PASSED")


def capture_read_only_queries(
    statements: list[str],
):
    def guard(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        normalized = statement.strip().upper()

        if not normalized.startswith("SELECT"):
            raise AssertionError(
                "Admin Statistics mencoba menjalankan "
                f"query non-SELECT: {normalized[:100]}"
            )

        statements.append(normalized)

    return guard


def test_admin_mysql_read_only_integration():
    require_safe_mysql()

    captured_sql = []

    with engine.connect() as connection:
        guard = capture_read_only_queries(
            captured_sql
        )

        event.listen(
            connection,
            "before_cursor_execute",
            guard,
        )

        try:
            with Session(
                bind=connection,
                autoflush=False,
                expire_on_commit=False,
            ) as session:
                repo = (
                    SqlAlchemyAdminStatisticsRepository(
                        session
                    )
                )

                stats = repo.get_system_statistics()

                assert stats.total_umkm >= 0
                assert stats.total_freelancers >= 0

                assert stats.total_projects >= 0

                assert stats.completed_projects <= (
                    stats.total_projects
                )

                assert stats.total_transactions >= 0
                assert stats.platform_income >= 0

                print(
                    "MYSQL SYSTEM STATISTICS: PASSED"
                )

                umkm_count = repo.count_users(
                    role="umkm",
                    search=None,
                )

                freelancer_count = repo.count_users(
                    role="freelancer",
                    search=None,
                )

                assert umkm_count == (
                    stats.total_umkm
                )

                assert freelancer_count == (
                    stats.total_freelancers
                )

                print(
                    "MYSQL USER COUNTS: PASSED"
                )

                users = repo.list_users(
                    role=None,
                    search=None,
                    limit=20,
                    offset=0,
                )

                total_users = repo.count_users(
                    role=None,
                    search=None,
                )

                assert len(users) <= 20
                assert len(users) <= total_users

                for user in users:
                    assert user.id
                    assert user.name
                    assert user.email

                    user_fields = asdict(user)

                    assert "password_hash" not in (
                        user_fields
                    )

                    assert "password" not in (
                        user_fields
                    )

                print(
                    "MYSQL USER LIST: PASSED"
                )

                for role in (
                    "umkm",
                    "freelancer",
                ):
                    filtered = repo.list_users(
                        role=role,
                        search=None,
                        limit=20,
                        offset=0,
                    )

                    for user in filtered:
                        assert user.role.lower() == role

                print(
                    "MYSQL USER ROLE FILTERS: PASSED"
                )

                if users:
                    selected_user = users[0]

                    detail = repo.get_user_detail(
                        selected_user.id
                    )

                    assert detail is not None

                    assert detail.user.id == (
                        selected_user.id
                    )

                    assert (
                        detail.user.role
                        == selected_user.role
                    )

                    detail_fields = asdict(
                        detail.user
                    )

                    assert "password_hash" not in (
                        detail_fields
                    )

                    print(
                        "MYSQL USER DETAIL: PASSED"
                    )

                else:
                    print(
                        "MYSQL USER DETAIL: "
                        "SKIPPED (database kosong)"
                    )

                project_count = repo.count_projects(
                    status=None,
                    search=None,
                )

                assert project_count == (
                    stats.total_projects
                )

                completed_count = (
                    repo.count_projects(
                        status="SELESAI",
                        search=None,
                    )
                )

                assert completed_count == (
                    stats.completed_projects
                )

                print(
                    "MYSQL PROJECT COUNTS: PASSED"
                )

                projects = repo.list_projects(
                    status=None,
                    search=None,
                    limit=20,
                    offset=0,
                )

                assert len(projects) <= 20

                assert len(projects) <= (
                    project_count
                )

                for project in projects:
                    assert project.id
                    assert project.title

                    assert project.budget >= 0

                    assert project.umkm_id

                    assert project.status

                print(
                    "MYSQL PROJECT LIST: PASSED"
                )

                if projects:
                    selected_project = projects[0]

                    detail = repo.get_project_detail(
                        selected_project.id
                    )

                    assert detail is not None

                    assert detail.project.id == (
                        selected_project.id
                    )

                    assert detail.project.umkm_id == (
                        selected_project.umkm_id
                    )

                    if (
                        selected_project
                        .assigned_freelancer_id is None
                    ):
                        assert (
                            detail.project
                            .assigned_freelancer_id
                            is None
                        )

                    print(
                        "MYSQL PROJECT DETAIL: PASSED"
                    )

                else:
                    print(
                        "MYSQL PROJECT DETAIL: "
                        "SKIPPED (database kosong)"
                    )

                if projects:
                    sample_status = (
                        projects[0].status
                    )

                    filtered_projects = (
                        repo.list_projects(
                            status=sample_status,
                            search=None,
                            limit=20,
                            offset=0,
                        )
                    )

                    assert all(
                        project.status.upper()
                        == sample_status.upper()
                        for project in filtered_projects
                    )

                    print(
                        "MYSQL PROJECT STATUS FILTER: PASSED"
                    )

                payment_row = session.execute(
                    text(
                        """
                        SELECT
                            COUNT(*) AS total_transactions,
                            COALESCE(
                                SUM(
                                    CASE
                                        WHEN status = 'BERHASIL'
                                        THEN platform_fee_amount
                                        ELSE 0
                                    END
                                ),
                                0
                            ) AS platform_income
                        FROM payments
                        """
                    )
                ).mappings().one()

                assert (
                    int(payment_row["total_transactions"])
                    == stats.total_transactions
                )

                assert (
                    int(payment_row["platform_income"])
                    == stats.platform_income
                )

                print(
                    "MYSQL PAYMENT AGGREGATION: PASSED"
                )

                if users:
                    keyword = users[0].name[:5]

                    search_count = repo.count_users(
                        role=None,
                        search=keyword,
                    )

                    assert search_count >= 1

                if projects:
                    keyword = projects[0].title[:5]

                    search_count = repo.count_projects(
                        status=None,
                        search=keyword,
                    )

                    assert search_count >= 1

                print(
                    "MYSQL SEARCH QUERIES: PASSED"
                )

        finally:
            event.remove(
                connection,
                "before_cursor_execute",
                guard,
            )

    assert captured_sql, (
        "Tidak ada SQL yang dieksekusi"
    )

    assert all(
        statement.startswith("SELECT")
        for statement in captured_sql
    )

    print("MYSQL READ-ONLY QUERIES: PASSED")

    print(
        "MYSQL SELECT QUERIES EXECUTED:",
        len(captured_sql),
    )

    print("MYSQL ADMIN INTEGRATION: PASSED")
