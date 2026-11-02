
from dataclasses import asdict

import pytest

from sqlalchemy import (
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import Session

from app.modules.matching.infrastructure.repositories import (
    SqlAlchemyMatchingRepository,
)


# ============================================================
# SQLITE TEST DATABASE
# ============================================================

@pytest.fixture
def context():
    """
    Menyiapkan database SQLite sementara
    untuk setiap test.

    Hanya kolom yang digunakan Repository
    yang dimasukkan ke dalam skema pengujian.
    """

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    # ========================================================
    # 1. CREATE TEST TABLES
    # ========================================================

    with engine.begin() as connection:

        schemas = (
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                email TEXT,
                password_hash TEXT
            )
            """,
            """
            CREATE TABLE freelancer_profiles (
                user_id TEXT PRIMARY KEY,
                professional_title TEXT NOT NULL,
                city TEXT NOT NULL,
                availability_status TEXT NOT NULL,
                service_price_min INTEGER,
                service_price_max INTEGER
            )
            """,
            """
            CREATE TABLE freelancer_skills (
                freelancer_id TEXT NOT NULL,
                skill_id TEXT NOT NULL,
                PRIMARY KEY (freelancer_id, skill_id)
            )
            """,
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                umkm_id TEXT NOT NULL,
                title TEXT NOT NULL,
                category_id TEXT NOT NULL,
                status TEXT NOT NULL,
                published_at TEXT
            )
            """,
            """
            CREATE TABLE project_skills (
                project_id TEXT NOT NULL,
                skill_id TEXT NOT NULL,
                PRIMARY KEY (project_id, skill_id)
            )
            """,
        )

        for schema in schemas:
            connection.execute(
                text(schema)
            )

        # ====================================================
        # 2. SEED USERS
        # ====================================================

        users = [
            {
                "id": "f1",
                "name": "Andi",
                "role": "freelancer",
                "email": "secret1@example.org",
                "password_hash": "TOPSECRET",
            },
            {
                "id": "f2",
                "name": "Budi",
                "role": "freelancer",
                "email": "secret2@example.org",
                "password_hash": "TOPSECRET",
            },
            {
                "id": "f3",
                "name": "Cici",
                "role": "freelancer",
                "email": "secret3@example.org",
                "password_hash": "TOPSECRET",
            },
            {
                "id": "f4",
                "name": "Dina",
                "role": "freelancer",
                "email": "secret4@example.org",
                "password_hash": "TOPSECRET",
            },
            {
                "id": "u1",
                "name": "UMKM",
                "role": "umkm",
                "email": "owner@example.org",
                "password_hash": "TOPSECRET",
            },
        ]

        connection.execute(
            text("""
                INSERT INTO users (
                    id, name, role,
                    email, password_hash
                )
                VALUES (
                    :id, :name, :role,
                    :email, :password_hash
                )
            """),
            users,
        )

        # ====================================================
        # 3. SEED FREELANCER PROFILES
        # ====================================================

        profiles = [
            {
                "id": "f1",
                "title": "Developer",
                "city": "Malang",
                "status": "AVAILABLE",
                "lo": 500000,
                "hi": 1500000,
            },
            {
                "id": "f2",
                "title": "Designer",
                "city": "Bandung",
                "status": "AVAILABLE",
                "lo": None,
                "hi": None,
            },
            {
                "id": "f3",
                "title": "Engineer",
                "city": "Malang",
                "status": "BUSY",
                "lo": 250000,
                "hi": 750000,
            },
            {
                "id": "f4",
                "title": "Newbie",
                "city": "Malang",
                "status": "AVAILABLE",
                "lo": None,
                "hi": None,
            },
            {
                "id": "u1",
                "title": "Fake Freelancer",
                "city": "Malang",
                "status": "AVAILABLE",
                "lo": 0,
                "hi": 0,
            },
        ]

        connection.execute(
            text("""
                INSERT INTO freelancer_profiles (
                    user_id,
                    professional_title,
                    city,
                    availability_status,
                    service_price_min,
                    service_price_max
                )
                VALUES (
                    :id, :title, :city,
                    :status, :lo, :hi
                )
            """),
            profiles,
        )

        # ====================================================
        # 4. SEED FREELANCER SKILLS
        # ====================================================

        connection.execute(
            text("""
                INSERT INTO freelancer_skills (
                    freelancer_id, skill_id
                )
                VALUES (
                    :id, :skill
                )
            """),
            [
                {"id": "f1", "skill": "python"},
                {"id": "f1", "skill": "fastapi"},
                {"id": "f1", "skill": "mysql"},
                {"id": "f2", "skill": "design"},
                {"id": "f3", "skill": "python"},
            ],
        )

        # ====================================================
        # 5. SEED PROJECTS
        # ====================================================

        projects = [
            {
                "id": "p1",
                "owner": "u1",
                "title": "Website",
                "cat": "website",
                "status": "TERBUKA",
                "published": "2026-11-01 10:00:00",
            },
            {
                "id": "p2",
                "owner": "u1",
                "title": "Backend API",
                "cat": "website",
                "status": "TERBUKA",
                "published": "2026-11-02 10:00:00",
            },
            {
                "id": "p3",
                "owner": "u1",
                "title": "Draft",
                "cat": "website",
                "status": "DRAFT",
                "published": None,
            },
            {
                "id": "p4",
                "owner": "u1",
                "title": "Unpublished",
                "cat": "website",
                "status": "TERBUKA",
                "published": None,
            },
            {
                "id": "p5",
                "owner": "u1",
                "title": "Closed",
                "cat": "website",
                "status": "SELESAI",
                "published": "2026-10-01 10:00:00",
            },
            {
                "id": "p6",
                "owner": "u1",
                "title": "Empty Skills",
                "cat": "website",
                "status": "TERBUKA",
                "published": "2026-10-31 10:00:00",
            },
        ]

        connection.execute(
            text("""
                INSERT INTO projects (
                    id, umkm_id, title,
                    category_id, status, published_at
                )
                VALUES (
                    :id, :owner, :title,
                    :cat, :status, :published
                )
            """),
            projects,
        )

        # ====================================================
        # 6. SEED PROJECT SKILLS
        # ====================================================

        connection.execute(
            text("""
                INSERT INTO project_skills (
                    project_id, skill_id
                )
                VALUES (
                    :id, :skill
                )
            """),
            [
                {"id": "p1", "skill": "python"},
                {"id": "p1", "skill": "fastapi"},
                {"id": "p1", "skill": "mysql"},
                {"id": "p2", "skill": "python"},
                {"id": "p2", "skill": "fastapi"},
                {"id": "p3", "skill": "design"},
                {"id": "p4", "skill": "python"},
                {"id": "p5", "skill": "python"},
            ],
        )

    # ========================================================
    # 7. RETURN REPOSITORY AND SESSION
    # ========================================================

    try:
        with Session(engine) as session:

            repository = (
                SqlAlchemyMatchingRepository(
                    session
                )
            )

            yield repository, session, engine

    finally:
        engine.dispose()


# ============================================================
# TEST 1 - GET PROJECT DATA
# ============================================================

def test_get_project_reads_ownership_category_status_and_skills(
    context,
):
    repo, _, _ = context

    project = repo.get_project("p1")

    assert (
        project.project_id,
        project.umkm_id,
        project.title,
        project.category_id,
        project.status,
    ) == (
        "p1",
        "u1",
        "Website",
        "website",
        "TERBUKA",
    )

    assert project.required_skill_ids == (
        "fastapi",
        "mysql",
        "python",
    )


# ============================================================
# TEST 2 - GET DRAFT FOR OWNERSHIP VALIDATION
# ============================================================

def test_get_project_can_load_draft_for_owner_validation(
    context,
):
    repo, _, _ = context

    project = repo.get_project("p3")

    assert project.status == "DRAFT"


# ============================================================
# TEST 3 - UNKNOWN PROJECT
# ============================================================

def test_get_project_missing_returns_none(
    context,
):
    repo, _, _ = context

    assert repo.get_project(
        "unknown"
    ) is None


# ============================================================
# TEST 4 - FREELANCER PROFILE AND SKILLS
# ============================================================

def test_get_freelancer_includes_skills_and_price(
    context,
):
    repo, _, _ = context

    freelancer = repo.get_freelancer("f1")

    assert (
        freelancer.name,
        freelancer.professional_title,
        freelancer.city,
        freelancer.availability_status,
    ) == (
        "Andi",
        "Developer",
        "Malang",
        "AVAILABLE",
    )

    assert freelancer.skill_ids == (
        "fastapi",
        "mysql",
        "python",
    )

    assert freelancer.service_price_min == 500000
    assert freelancer.service_price_max == 1500000


# ============================================================
# TEST 5 - BUSY FREELANCER CAN BE READ
# ============================================================

def test_get_freelancer_busy_is_still_readable(
    context,
):
    repo, _, _ = context

    freelancer = repo.get_freelancer("f3")

    assert freelancer.availability_status == "BUSY"


# ============================================================
# TEST 6 - UNKNOWN / WRONG ROLE
# ============================================================

def test_get_freelancer_missing_and_wrong_role(
    context,
):
    repo, _, _ = context

    assert repo.get_freelancer(
        "unknown"
    ) is None

    assert repo.get_freelancer(
        "u1"
    ) is None


# ============================================================
# TEST 7 - AVAILABLE FREELANCERS
# ============================================================

def test_available_freelancers_are_filtered_and_deterministic(
    context,
):
    repo, _, _ = context

    freelancers = repo.iter_available_freelancers()

    assert [
        item.freelancer_id
        for item in freelancers
    ] == [
        "f1",
        "f2",
        "f4",
    ]


# ============================================================
# TEST 8 - FREELANCER WITHOUT SKILLS
# ============================================================

def test_available_freelancer_with_no_skills(
    context,
):
    repo, _, _ = context

    freelancers = repo.iter_available_freelancers()

    assert freelancers[-1].skill_ids == ()


# ============================================================
# TEST 9 - PUBLISHED PROJECTS ONLY
# ============================================================

def test_published_projects_require_timestamp_and_open_status(
    context,
):
    repo, _, _ = context

    projects = repo.iter_published_projects()

    assert [
        item.project_id
        for item in projects
    ] == [
        "p2",
        "p1",
        "p6",
    ]


# ============================================================
# TEST 10 - PROJECT WITHOUT SKILLS
# ============================================================

def test_published_project_with_no_skills(
    context,
):
    repo, _, _ = context

    projects = repo.iter_published_projects()

    assert projects[-1].required_skill_ids == ()


# ============================================================
# TEST 11 - NO DUPLICATE SKILLS
# ============================================================

def test_candidate_skill_sets_no_duplicates(
    context,
):
    repo, _, _ = context

    freelancer = repo.get_freelancer("f1")
    project = repo.get_project("p1")

    assert len(freelancer.skill_ids) == 3
    assert len(project.required_skill_ids) == 3


# ============================================================
# TEST 12 - DATA LEAK PROTECTION
# ============================================================

def test_repository_does_not_expose_sensitive_user_data(
    context,
):
    repo, _, _ = context

    rendered = repr([
        asdict(item)
        for item in repo.iter_available_freelancers()
    ])

    assert "TOPSECRET" not in rendered
    assert "password_hash" not in rendered
    assert "secret1@" not in rendered


# ============================================================
# TEST 13 - READ ONLY
# ============================================================

def test_repository_only_reads_data(
    context,
):
    repo, session, _ = context

    before = session.execute(
        text("SELECT COUNT(*) FROM projects")
    ).scalar_one()

    repo.get_project("p1")
    repo.get_freelancer("f1")
    repo.iter_available_freelancers()
    repo.iter_published_projects()

    after = session.execute(
        text("SELECT COUNT(*) FROM projects")
    ).scalar_one()

    assert before == after

    assert not session.new
    assert not session.dirty
    assert not session.deleted


# ============================================================
# TEST 14 - PARAMETERIZED SQL LOOKUPS
# ============================================================

def test_parameterized_lookup_resists_injection(
    context,
):
    repo, _, _ = context

    assert repo.get_project(
        "p1' OR '1'='1"
    ) is None

    assert repo.get_freelancer(
        "f1' OR '1'='1"
    ) is None


# ============================================================
# TEST 15 - PREVENT N+1 QUERY
# ============================================================

def test_bulk_fetch_does_not_n_plus_one(
    context,
):
    repo, _, engine = context

    statements = []

    def trace(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        statements.append(statement)

    event.listen(
        engine,
        "before_cursor_execute",
        trace,
    )

    try:
        repo.iter_available_freelancers()

        # 1 query profil, 1 query skills
        assert len(statements) == 2

        statements.clear()

        repo.iter_published_projects()

        # 1 query project, 1 query skills
        assert len(statements) == 2

    finally:
        event.remove(
            engine,
            "before_cursor_execute",
            trace,
        )


# ============================================================
# TEST 16 - EMPTY CANDIDATES
# ============================================================

def test_empty_candidate_queries_skip_skills_lookup(
    context,
):
    repo, session, _ = context

    session.execute(
        text("DELETE FROM freelancer_profiles")
    )

    session.execute(
        text("DELETE FROM projects")
    )

    assert repo.iter_available_freelancers() == []
    assert repo.iter_published_projects() == []