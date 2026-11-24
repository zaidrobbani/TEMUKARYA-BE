
import pytest

from app.modules.admin_statistics.domain.entities import (
    AdminActor,
    AdminSystemStatistics,
)

from app.modules.admin_statistics.domain.statistics_rules import (
    require_admin_actor,
    validate_identifier,
    validate_pagination,
    normalize_search_query,
    normalize_user_role_filter,
    normalize_project_status_filter,
    validate_non_negative_integer,
    build_system_statistics,
)


# ============================================================
# 1. TEST DATA
# ============================================================

def valid_stats():
    return {
        "total_umkm": 10,
        "total_freelancers": 20,
        "total_projects": 15,
        "completed_projects": 5,
        "total_transactions": 7,
        "platform_income": 350000,
    }


# ============================================================
# 2. ADMIN AUTHORIZATION - VALID
# ============================================================

@pytest.mark.parametrize(
    "role",
    [
        "admin",
        "ADMIN",
        " Admin ",
    ],
)
def test_valid_admin_actor(role):
    actor = AdminActor(
        user_id="admin-001",
        role=role,
    )

    require_admin_actor(actor)


# ============================================================
# 3. ADMIN AUTHORIZATION - WRONG ROLE
# ============================================================

@pytest.mark.parametrize(
    "role",
    [
        "umkm",
        "freelancer",
        "guest",
        "",
    ],
)
def test_non_admin_role_rejected(role):
    actor = AdminActor(
        user_id="user-001",
        role=role,
    )

    with pytest.raises(PermissionError):
        require_admin_actor(actor)


# ============================================================
# 4. ADMIN AUTHORIZATION - INVALID IDENTITY
# ============================================================

@pytest.mark.parametrize(
    "actor",
    [
        None,
        "admin",
        123,
        AdminActor("", "admin"),
        AdminActor(" admin ", "admin"),
        AdminActor("a" * 37, "admin"),
        AdminActor("user/id", "admin"),
        AdminActor("admin-001", None),
    ],
)
def test_invalid_admin_identity_rejected(actor):
    with pytest.raises(PermissionError):
        require_admin_actor(actor)


# ============================================================
# 5. VALID IDENTIFIER
# ============================================================

@pytest.mark.parametrize(
    "value,expected",
    [
        ("abc", "abc"),
        ("a" * 36, "a" * 36),
        ("  user-001  ", "user-001"),
    ],
)
def test_valid_identifier(value, expected):
    assert validate_identifier(value) == expected


# ============================================================
# 6. INVALID IDENTIFIER
# ============================================================

@pytest.mark.parametrize(
    "value",
    [
        None,
        42,
        "",
        "   ",
        "a" * 37,
        "user/id",
        "user\\id",
        "user\x00id",
    ],
)
def test_invalid_identifier_rejected(value):
    with pytest.raises(ValueError):
        validate_identifier(value)


def test_identifier_custom_field_name():
    with pytest.raises(
        ValueError,
        match="Project ID",
    ):
        validate_identifier(
            "",
            "Project ID",
        )


# ============================================================
# 7. VALID PAGINATION
# ============================================================

@pytest.mark.parametrize(
    "limit,offset",
    [
        (1, 0),
        (20, 10),
        (100, 10000),
    ],
)
def test_valid_pagination(limit, offset):
    assert validate_pagination(
        limit,
        offset,
    ) == (limit, offset)


# ============================================================
# 8. INVALID LIMIT
# ============================================================

@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        101,
        True,
        False,
        "20",
        1.5,
        None,
    ],
)
def test_invalid_limit_rejected(limit):
    with pytest.raises(ValueError):
        validate_pagination(
            limit,
            0,
        )


# ============================================================
# 9. INVALID OFFSET
# ============================================================

@pytest.mark.parametrize(
    "offset",
    [
        -1,
        10001,
        True,
        False,
        "0",
        1.5,
        None,
    ],
)
def test_invalid_offset_rejected(offset):
    with pytest.raises(ValueError):
        validate_pagination(
            20,
            offset,
        )


# ============================================================
# 10. EMPTY SEARCH QUERY
# ============================================================

@pytest.mark.parametrize(
    "query",
    [
        None,
        "",
        "   ",
        "\n\t",
    ],
)
def test_empty_search_query(query):
    assert normalize_search_query(query) is None


# ============================================================
# 11. VALID SEARCH QUERY
# ============================================================

@pytest.mark.parametrize(
    "query,expected",
    [
        ("  desain logo  ", "desain logo"),
        ("a" * 100, "a" * 100),
    ],
)
def test_valid_search_query(query, expected):
    assert normalize_search_query(query) == expected


# ============================================================
# 12. INVALID SEARCH QUERY
# ============================================================

@pytest.mark.parametrize(
    "query",
    [
        123,
        "a" * 101,
        "abc\x00def",
    ],
)
def test_invalid_search_query_rejected(query):
    with pytest.raises(ValueError):
        normalize_search_query(query)


# ============================================================
# 13. EMPTY USER ROLE FILTER
# ============================================================

@pytest.mark.parametrize(
    "role",
    [
        None,
        "",
        "   ",
    ],
)
def test_empty_role_filter(role):
    assert normalize_user_role_filter(role) is None


# ============================================================
# 14. VALID USER ROLE FILTER
# ============================================================

@pytest.mark.parametrize(
    "role,expected",
    [
        ("UMKM", "umkm"),
        (" freelancer ", "freelancer"),
    ],
)
def test_valid_role_filter(role, expected):
    assert normalize_user_role_filter(
        role
    ) == expected


# ============================================================
# 15. INVALID USER ROLE FILTER
# ============================================================

@pytest.mark.parametrize(
    "role",
    [
        "admin",
        "guest",
        "umkm;drop",
        True,
        123,
    ],
)
def test_invalid_role_filter_rejected(role):
    with pytest.raises(ValueError):
        normalize_user_role_filter(role)


# ============================================================
# 16. EMPTY PROJECT STATUS FILTER
# ============================================================

@pytest.mark.parametrize(
    "status",
    [
        None,
        "",
        "   ",
    ],
)
def test_empty_project_status(status):
    assert (
        normalize_project_status_filter(status)
        is None
    )


# ============================================================
# 17. VALID PROJECT STATUS
# ============================================================

@pytest.mark.parametrize(
    "status,expected",
    [
        ("terbuka", "TERBUKA"),
        (" siap_dikerjakan ", "SIAP_DIKERJAKAN"),
        ("SELESAI", "SELESAI"),
    ],
)
def test_valid_project_status(status, expected):
    assert normalize_project_status_filter(
        status
    ) == expected


# ============================================================
# 18. INVALID PROJECT STATUS
# ============================================================

@pytest.mark.parametrize(
    "status",
    [
        "IN PROGRESS",
        "DROP;TABLE",
        "status-ke",
        "a" * 41,
        True,
    ],
)
def test_invalid_project_status_rejected(status):
    with pytest.raises(ValueError):
        normalize_project_status_filter(status)


# ============================================================
# 19. VALID NON-NEGATIVE INTEGERS
# ============================================================

@pytest.mark.parametrize(
    "value,field",
    [
        (0, "total_umkm"),
        (45, "total_projects"),
        (350000, "platform_income"),
    ],
)
def test_non_negative_integer(value, field):
    assert validate_non_negative_integer(
        value,
        field,
    ) == value


# ============================================================
# 20. INVALID NUMERIC VALUES
# ============================================================

@pytest.mark.parametrize(
    "value",
    [
        -1,
        True,
        False,
        1.5,
        "5",
        None,
    ],
)
def test_invalid_numeric_value_rejected(value):
    with pytest.raises(ValueError):
        validate_non_negative_integer(
            value,
            "total_projects",
        )


# ============================================================
# 21. VALID SYSTEM STATISTICS
# ============================================================

def test_build_system_statistics():
    result = build_system_statistics(
        **valid_stats()
    )

    assert isinstance(
        result,
        AdminSystemStatistics,
    )

    assert result.total_umkm == 10
    assert result.total_freelancers == 20
    assert result.total_projects == 15
    assert result.completed_projects == 5
    assert result.total_transactions == 7
    assert result.platform_income == 350000


# ============================================================
# 22. EMPTY SYSTEM STATISTICS
# ============================================================

def test_build_zero_statistics():
    result = build_system_statistics(
        total_umkm=0,
        total_freelancers=0,
        total_projects=0,
        completed_projects=0,
        total_transactions=0,
        platform_income=0,
    )

    assert result.total_umkm == 0
    assert result.total_projects == 0
    assert result.platform_income == 0


# ============================================================
# 23. COMPLETED PROJECTS EXCEED TOTAL
# ============================================================

def test_completed_projects_cannot_exceed_total():
    values = valid_stats()

    values["total_projects"] = 2
    values["completed_projects"] = 3

    with pytest.raises(ValueError):
        build_system_statistics(**values)


# ============================================================
# 24. REJECT NEGATIVE STATISTICS
# ============================================================

@pytest.mark.parametrize(
    "field",
    [
        "total_umkm",
        "total_freelancers",
        "total_projects",
        "completed_projects",
        "total_transactions",
        "platform_income",
    ],
)
def test_negative_statistic_rejected(field):
    values = valid_stats()

    values[field] = -1

    with pytest.raises(ValueError):
        build_system_statistics(**values)


# ============================================================
# 25. REJECT BOOLEAN STATISTICS
# ============================================================

@pytest.mark.parametrize(
    "field",
    [
        "total_umkm",
        "total_freelancers",
        "total_projects",
        "completed_projects",
        "total_transactions",
        "platform_income",
    ],
)
def test_boolean_statistic_rejected(field):
    values = valid_stats()

    values[field] = True

    with pytest.raises(ValueError):
        build_system_statistics(**values)