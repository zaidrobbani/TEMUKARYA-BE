
from datetime import date, datetime, timezone

import pytest

from sqlalchemy import (
    create_engine,
    event,
    text,
)

from sqlalchemy.orm import Session

from app.modules.admin_statistics.infrastructure.repositories import (
    SqlAlchemyAdminStatisticsRepository,
)


# ============================================================
# 1. SQLITE TEST DATABASE
# ============================================================

@pytest.fixture
def db():
    """
    Database SQLite sementara.

    Semua tabel dan data dibuat hanya untuk test.
    """

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    with engine.begin() as conn:

        # ----------------------------------------------------
        # CREATE TEST TABLES
        # ----------------------------------------------------

        statements = [
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at DATETIME NOT NULL
            )
            """,
            """
            CREATE TABLE umkm_profiles (
                user_id TEXT PRIMARY KEY,
                business_name TEXT,
                business_category TEXT,
                business_address TEXT,
                city TEXT
            )
            """,
            """
            CREATE TABLE freelancer_profiles (
                user_id TEXT PRIMARY KEY,
                professional_title TEXT,
                bio TEXT,
                city TEXT,
                service_price_min INTEGER,
                service_price_max INTEGER,
                availability_status TEXT
            )
            """,
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                title TEXT,
                category_id TEXT,
                umkm_id TEXT,
                budget INTEGER,
                deadline DATE,
                status TEXT,
                created_at DATETIME,
                description TEXT,
                published_at DATETIME,
                started_at DATETIME,
                completed_at DATETIME
            )
            """,
            """
            CREATE TABLE project_agreements (
                id TEXT PRIMARY KEY,
                project_id TEXT UNIQUE,
                freelancer_id TEXT,
                agreed_price INTEGER
            )
            """,
            """
            CREATE TABLE payments (
                id TEXT PRIMARY KEY,
                agreement_id TEXT,
                platform_fee_amount INTEGER,
                status TEXT
            )
            """,
        ]

        for statement in statements:
            conn.execute(
                text(statement)
            )

        # ----------------------------------------------------
        # INSERT TEST USERS
        # ----------------------------------------------------

        conn.execute(
            text(
                """
                INSERT INTO users
                VALUES (
                    :id,
                    :name,
                    :email,
                    :pass,
                    :role,
                    :created
                )
                """
            ),
            [
                {
                    "id": "u1",
                    "name": "Toko 100% _ Craft",
                    "email": "u1@x.test",
                    "pass": "super-secret",
                    "role": "umkm",
                    "created": "2026-01-04 10:00:00",
                },
                {
                    "id": "u2",
                    "name": "UMKM Dua",
                    "email": "u2@x.test",
                    "pass": "super-secret",
                    "role": "umkm",
                    "created": "2026-01-05 10:00:00",
                },
                {
                    "id": "f1",
                    "name": "Freelancer Satu",
                    "email": "f1@x.test",
                    "pass": "super-secret",
                    "role": "freelancer",
                    "created": "2026-01-06 10:00:00",
                },
                {
                    "id": "f2",
                    "name": "Freelancer! Dua",
                    "email": "f2@x.test",
                    "pass": "super-secret",
                    "role": "freelancer",
                    "created": "2026-01-07 10:00:00",
                },
                {
                    "id": "admin1",
                    "name": "Admin",
                    "email": "admin@x.test",
                    "pass": "super-secret",
                    "role": "admin",
                    "created": "2026-01-08 10:00:00",
                },
            ],
        )

        # ----------------------------------------------------
        # INSERT UMKM PROFILE
        # ----------------------------------------------------

        conn.execute(
            text(
                """
                INSERT INTO umkm_profiles
                VALUES (
                    'u1',
                    'Usaha Digital',
                    'Teknologi',
                    'Malang',
                    'Malang'
                )
                """
            )
        )

        # ----------------------------------------------------
        # INSERT FREELANCER PROFILE
        # ----------------------------------------------------

        conn.execute(
            text(
                """
                INSERT INTO freelancer_profiles
                VALUES (
                    'f1',
                    'Designer',
                    NULL,
                    'Malang',
                    100000,
                    500000,
                    'AVAILABLE'
                )
                """
            )
        )

        # ----------------------------------------------------
        # INSERT TEST PROJECTS
        # ----------------------------------------------------

        conn.execute(
            text(
                """
                INSERT INTO projects
                VALUES (
                    :id,
                    :title,
                    'cat1',
                    :owner,
                    :budget,
                    '2026-12-01',
                    :status,
                    :created,
                    :description,
                    :published,
                    :started,
                    :completed
                )
                """
            ),
            [
                {
                    "id": "p1",
                    "title": "Website UMKM",
                    "owner": "u1",
                    "budget": 2000000,
                    "status": "TERBUKA",
                    "created": "2026-02-01 09:00:00",
                    "description": "Membuat website",
                    "published": None,
                    "started": None,
                    "completed": None,
                },
                {
                    "id": "p2",
                    "title": "Logo 100% _ Keren",
                    "owner": "u2",
                    "budget": 400000,
                    "status": "SELESAI",
                    "created": "2026-02-02 09:00:00",
                    "description": "Bikin logo",
                    "published": "2026-02-02 10:00:00",
                    "started": "2026-02-03 09:00:00",
                    "completed": "2026-02-04 12:00:00",
                },
                {
                    "id": "p3",
                    "title": "Mobile App",
                    "owner": "u1",
                    "budget": 600000,
                    "status": "SIAP_DIKERJAKAN",
                    "created": "2026-02-03 09:00:00",
                    "description": "Bikin app",
                    "published": "2026-02-03 10:00:00",
                    "started": None,
                    "completed": None,
                },
                {
                    "id": "p4",
                    "title": "Marketing",
                    "owner": "u2",
                    "budget": 500000,
                    "status": "TERBUKA",
                    "created": "2026-02-04 09:00:00",
                    "description": "Social media",
                    "published": None,
                    "started": None,
                    "completed": None,
                },
            ],
        )

        # ----------------------------------------------------
        # INSERT TEST AGREEMENTS
        # ----------------------------------------------------

        conn.execute(
            text(
                """
                INSERT INTO project_agreements
                VALUES (
                    :id,
                    :project_id,
                    :freelancer_id,
                    :agreed_price
                )
                """
            ),
            [
                {
                    "id": "a2",
                    "project_id": "p2",
                    "freelancer_id": "f1",
                    "agreed_price": 350000,
                },
                {
                    "id": "a3",
                    "project_id": "p3",
                    "freelancer_id": "f2",
                    "agreed_price": 550000,
                },
                {
                    "id": "a4",
                    "project_id": "p4",
                    "freelancer_id": "f1",
                    "agreed_price": 490000,
                },
            ],
        )

        # ----------------------------------------------------
        # INSERT TEST PAYMENTS
        # ----------------------------------------------------

        conn.execute(
            text(
                """
                INSERT INTO payments
                VALUES (
                    :id,
                    :agreement_id,
                    :platform_fee_amount,
                    :status
                )
                """
            ),
            [
                {
                    "id": "pay2",
                    "agreement_id": "a2",
                    "platform_fee_amount": 7500,
                    "status": "BERHASIL",
                },
                {
                    "id": "pay3",
                    "agreement_id": "a3",
                    "platform_fee_amount": 12500,
                    "status": "BERHASIL",
                },
                {
                    "id": "pay4",
                    "agreement_id": "a4",
                    "platform_fee_amount": 3500,
                    "status": "MENUNGGU",
                },
            ],
        )

    # --------------------------------------------------------
    # PROVIDE SESSION AND REPOSITORY
    # --------------------------------------------------------

    try:
        with Session(engine) as session:

            repository = (
                SqlAlchemyAdminStatisticsRepository(
                    session
                )
            )

            yield session, repository

    finally:
        engine.dispose()


# ============================================================
# 2. LIST USERS ORDERING
# ============================================================

def test_list_users_order(db):

    _, repo = db

    items = repo.list_users(
        role=None,
        search=None,
        limit=3,
        offset=0,
    )

    assert [
        user.id
        for user in items
    ] == [
        "admin1",
        "f2",
        "f1",
    ]


# ============================================================
# 3. COUNT USERS
# ============================================================

def test_count_users(db):

    _, repo = db

    assert repo.count_users(
        role=None,
        search=None,
    ) == 5

    assert repo.count_users(
        role="umkm",
        search=None,
    ) == 2

    assert repo.count_users(
        role="freelancer",
        search=None,
    ) == 2


# ============================================================
# 4. USER SEARCH BY EMAIL
# ============================================================

def test_user_search_email(db):

    _, repo = db

    items = repo.list_users(
        role=None,
        search="F1@",
        limit=10,
        offset=0,
    )

    assert [
        user.id
        for user in items
    ] == ["f1"]


# ============================================================
# 5. SEARCH ESCAPING
# ============================================================

def test_user_search_wildcards(db):

    _, repo = db

    cases = [
        ("%", ["u1"]),
        ("_", ["u1"]),
        ("!", ["f2"]),
    ]

    for search, expected in cases:

        items = repo.list_users(
            role=None,
            search=search,
            limit=10,
            offset=0,
        )

        assert [
            item.id
            for item in items
        ] == expected

        assert repo.count_users(
            role=None,
            search=search,
        ) == 1


# ============================================================
# 6. GET UMKM DETAIL
# ============================================================

def test_user_detail_umkm(db):

    _, repo = db

    detail = repo.get_user_detail("u1")

    assert detail is not None

    assert detail.umkm_profile.business_name == (
        "Usaha Digital"
    )

    assert detail.freelancer_profile is None

    assert "password_hash" not in str(detail)


# ============================================================
# 7. GET FREELANCER DETAIL
# ============================================================

def test_user_detail_freelancer(db):

    _, repo = db

    detail = repo.get_user_detail("f1")

    assert detail is not None

    assert detail.freelancer_profile.service_price_min == (
        100000
    )

    assert detail.umkm_profile is None


# ============================================================
# 8. GET ADMIN USER DETAIL
# ============================================================

def test_user_detail_admin(db):

    _, repo = db

    detail = repo.get_user_detail("admin1")

    assert detail is not None
    assert detail.umkm_profile is None
    assert detail.freelancer_profile is None


# ============================================================
# 9. MISSING USER
# ============================================================

def test_user_detail_missing(db):

    _, repo = db

    assert repo.get_user_detail("missing") is None


# ============================================================
# 10. LIST PROJECTS
# ============================================================

def test_list_projects(db):

    _, repo = db

    items = repo.list_projects(
        status=None,
        search=None,
        limit=10,
        offset=0,
    )

    assert [
        project.id
        for project in items
    ] == [
        "p4",
        "p3",
        "p2",
        "p1",
    ]

    assert items[-1].assigned_freelancer_id is None

    assert items[0].assigned_freelancer_id == "f1"


# ============================================================
# 11. PROJECT STATUS FILTER
# ============================================================

def test_project_filter(db):

    _, repo = db

    assert repo.count_projects(
        status="TERBUKA",
        search=None,
    ) == 2

    assert repo.count_projects(
        status="SELESAI",
        search=None,
    ) == 1

    items = repo.list_projects(
        status="SELESAI",
        search=None,
        limit=10,
        offset=0,
    )

    assert [
        project.id
        for project in items
    ] == ["p2"]


# ============================================================
# 12. PROJECT SEARCH ESCAPING
# ============================================================

def test_project_search_wildcards(db):

    _, repo = db

    for search in ["%", "_"]:

        items = repo.list_projects(
            status=None,
            search=search,
            limit=10,
            offset=0,
        )

        assert [
            project.id
            for project in items
        ] == ["p2"]

        assert repo.count_projects(
            status=None,
            search=search,
        ) == 1


# ============================================================
# 13. PROJECT DETAIL WITH AGREEMENT
# ============================================================

def test_project_detail_agreement(db):

    _, repo = db

    detail = repo.get_project_detail("p2")

    assert detail is not None

    assert detail.agreed_price == 350000

    assert detail.project.assigned_freelancer_name == (
        "Freelancer Satu"
    )

    assert detail.completed_at.year == 2026


# ============================================================
# 14. PROJECT DETAIL WITHOUT AGREEMENT
# ============================================================

def test_project_detail_without_agreement(db):

    _, repo = db

    detail = repo.get_project_detail("p1")

    assert detail is not None

    assert detail.agreed_price is None

    assert (
        detail.project.assigned_freelancer_id
        is None
    )

    assert detail.started_at is None


# ============================================================
# 15. MISSING PROJECT
# ============================================================

def test_project_detail_missing(db):

    _, repo = db

    assert repo.get_project_detail("missing") is None


# ============================================================
# 16. SYSTEM STATISTICS
# ============================================================

def test_system_stats(db):

    _, repo = db

    stats = repo.get_system_statistics()

    assert (
        stats.total_umkm,
        stats.total_freelancers,
        stats.total_projects,
        stats.completed_projects,
        stats.total_transactions,
        stats.platform_income,
    ) == (
        2,
        2,
        4,
        1,
        3,
        20000,
    )


# ============================================================
# 17. EMPTY PAYMENTS
# ============================================================

def test_zero_payments(db):

    session, repo = db

    # Data test diubah pada fixture SQLite.
    # Repository Admin tetap read-only.
    session.execute(
        text("DELETE FROM payments")
    )

    stats = repo.get_system_statistics()

    assert stats.total_transactions == 0
    assert stats.platform_income == 0


# ============================================================
# 18. VERIFY READ-ONLY QUERIES
# ============================================================

def test_methods_are_read_only(db):

    session, repo = db

    statements = []

    # Catat seluruh SQL yang dieksekusi
    # saat metode Repository dipanggil.
    @event.listens_for(
        session.bind,
        "before_cursor_execute",
    )
    def capture_sql(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        statements.append(
            statement.lstrip().upper()
        )

    try:

        repo.list_users(
            role=None,
            search=None,
            limit=10,
            offset=0,
        )

        repo.get_user_detail("u1")

        repo.list_projects(
            status=None,
            search=None,
            limit=10,
            offset=0,
        )

        repo.get_project_detail("p2")

        repo.get_system_statistics()

    finally:
        event.remove(
            session.bind,
            "before_cursor_execute",
            capture_sql,
        )

    assert statements

    assert all(
        statement.startswith("SELECT")
        for statement in statements
    )