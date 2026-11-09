from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

from app.modules.admin_statistics.application.dto import (
    GetAdminProjectInput,
    GetAdminStatisticsInput,
    GetAdminUserInput,
    ListAdminProjectsInput,
    ListAdminUsersInput,
)

from app.modules.admin_statistics.application.use_cases import (
    GetAdminProject,
    GetAdminStatistics,
    GetAdminUser,
    ListAdminProjects,
    ListAdminUsers,
)

from app.modules.admin_statistics.domain.entities import (
    AdminActor,
    AdminFreelancerProfile,
    AdminProjectDetail,
    AdminProjectSummary,
    AdminSystemStatistics,
    AdminUMKMProfile,
    AdminUserDetail,
    AdminUserSummary,
)


# ============================================================
# 1. TEST CONSTANTS
# ============================================================

NOW = datetime(
    2026, 11, 4, 10, 0,
    tzinfo=timezone.utc,
)

DEADLINE = date(2026, 12, 1)

ADMIN = AdminActor(
    user_id="admin-001",
    role="admin",
)

UMKM_ACTOR = AdminActor(
    user_id="u1",
    role="umkm",
)

FREELANCER_ACTOR = AdminActor(
    user_id="f1",
    role="freelancer",
)


# ============================================================
# 2. TEST DATA HELPERS
# ============================================================

def make_user(
    user_id: str,
    name: str,
    role: str,
) -> AdminUserSummary:

    return AdminUserSummary(
        id=user_id,
        name=name,
        email=f"{user_id}@example.com",
        role=role,
        created_at=NOW,
    )


def make_project(
    project_id: str,
    title: str,
    status: str,
    assigned: bool = False,
) -> AdminProjectSummary:

    return AdminProjectSummary(
        id=project_id,
        title=title,
        category_id="technology",
        umkm_id="u1",
        umkm_name="UMKM Digital",
        assigned_freelancer_id=(
            "f1" if assigned else None
        ),
        assigned_freelancer_name=(
            "Freelancer Satu" if assigned else None
        ),
        budget=2000000,
        deadline=DEADLINE,
        status=status,
        created_at=NOW,
    )


# ============================================================
# 3. FAKE ADMIN STATISTICS REPOSITORY
# ============================================================

class FakeAdminStatisticsRepository:
    """
    Fake Repository untuk unit testing.

    Tidak terhubung ke MySQL.

    Semua fungsi hanya melakukan pembacaan
    terhadap data simulasi.
    """

    def __init__(self):

        self.users = (
            make_user(
                "u1",
                "UMKM Satu",
                "umkm",
            ),
            make_user(
                "f1",
                "Freelancer Satu",
                "freelancer",
            ),
            make_user(
                "a1",
                "Admin Sistem",
                "admin",
            ),
        )

        self.projects = (
            make_project(
                "p1",
                "Website UMKM",
                "TERBUKA",
            ),
            make_project(
                "p2",
                "Desain Logo",
                "SELESAI",
                assigned=True,
            ),
        )

        self.user_details = {
            "u1": AdminUserDetail(
                user=self.users[0],
                umkm_profile=AdminUMKMProfile(
                    business_name="UMKM Digital",
                    business_category="Technology",
                    business_address="Malang",
                    city="Malang",
                ),
            ),
            "f1": AdminUserDetail(
                user=self.users[1],
                freelancer_profile=AdminFreelancerProfile(
                    professional_title="Designer",
                    bio="Freelancer kreatif",
                    city="Malang",
                    service_price_min=100000,
                    service_price_max=1000000,
                    availability_status="AVAILABLE",
                ),
            ),
            "a1": AdminUserDetail(
                user=self.users[2],
            ),
        }

        self.project_details = {
            "p1": AdminProjectDetail(
                project=self.projects[0],
                description="Membuat website UMKM",
                agreed_price=None,
                published_at=NOW,
                started_at=None,
                completed_at=None,
            ),
            "p2": AdminProjectDetail(
                project=self.projects[1],
                description="Mendesain logo bisnis",
                agreed_price=1800000,
                published_at=NOW,
                started_at=NOW,
                completed_at=NOW,
            ),
        }

        self.statistics = AdminSystemStatistics(
            total_umkm=1,
            total_freelancers=1,
            total_projects=2,
            completed_projects=1,
            total_transactions=3,
            platform_income=90000,
        )

        # Digunakan untuk mensimulasikan error.
        self.override_users = None
        self.override_projects = None
        self.override_user_detail = None
        self.override_project_detail = None
        self.override_statistics = None

        self.override_user_count = None
        self.override_project_count = None

        self.calls = []

    # ========================================================
    # A. FILTER USERS
    # ========================================================

    def _filtered_users(
        self,
        *,
        role,
        search,
    ):

        items = list(self.users)

        if role is not None:
            items = [
                user
                for user in items
                if user.role == role
            ]

        if search is not None:
            keyword = search.casefold()

            items = [
                user
                for user in items
                if (
                    keyword in user.name.casefold()
                    or keyword in user.email.casefold()
                )
            ]

        return tuple(items)

    # ========================================================
    # B. LIST USERS
    # ========================================================

    def list_users(
        self,
        *,
        role,
        search,
        limit,
        offset,
    ):

        self.calls.append(
            ("list_users", role, search, limit, offset)
        )

        if self.override_users is not None:
            return self.override_users

        items = self._filtered_users(
            role=role,
            search=search,
        )

        return items[offset:offset + limit]

    # ========================================================
    # C. COUNT USERS
    # ========================================================

    def count_users(
        self,
        *,
        role,
        search,
    ):

        self.calls.append(
            ("count_users", role, search)
        )

        if self.override_user_count is not None:
            return self.override_user_count

        return len(
            self._filtered_users(
                role=role,
                search=search,
            )
        )

    # ========================================================
    # D. USER DETAIL
    # ========================================================

    def get_user_detail(
        self,
        user_id,
    ):

        self.calls.append(
            ("get_user_detail", user_id)
        )

        if self.override_user_detail is not None:
            return self.override_user_detail

        return self.user_details.get(
            user_id
        )

    # ========================================================
    # E. FILTER PROJECTS
    # ========================================================

    def _filtered_projects(
        self,
        *,
        status,
        search,
    ):

        items = list(self.projects)

        if status is not None:
            items = [
                project
                for project in items
                if project.status == status
            ]

        if search is not None:
            keyword = search.casefold()

            items = [
                project
                for project in items
                if keyword in project.title.casefold()
            ]

        return tuple(items)

    # ========================================================
    # F. LIST PROJECTS
    # ========================================================

    def list_projects(
        self,
        *,
        status,
        search,
        limit,
        offset,
    ):

        self.calls.append(
            (
                "list_projects",
                status,
                search,
                limit,
                offset,
            )
        )

        if self.override_projects is not None:
            return self.override_projects

        items = self._filtered_projects(
            status=status,
            search=search,
        )

        return items[offset:offset + limit]

    # ========================================================
    # G. COUNT PROJECTS
    # ========================================================

    def count_projects(
        self,
        *,
        status,
        search,
    ):

        self.calls.append(
            ("count_projects", status, search)
        )

        if self.override_project_count is not None:
            return self.override_project_count

        return len(
            self._filtered_projects(
                status=status,
                search=search,
            )
        )

    # ========================================================
    # H. PROJECT DETAIL
    # ========================================================

    def get_project_detail(
        self,
        project_id,
    ):

        self.calls.append(
            ("get_project_detail", project_id)
        )

        if self.override_project_detail is not None:
            return self.override_project_detail

        return self.project_details.get(
            project_id
        )

    # ========================================================
    # I. SYSTEM STATISTICS
    # ========================================================

    def get_system_statistics(self):

        self.calls.append(
            ("get_system_statistics",)
        )

        if self.override_statistics is not None:
            return self.override_statistics

        return self.statistics


# ============================================================
# 4. PYTEST FIXTURE
# ============================================================

@pytest.fixture
def repo():
    return FakeAdminStatisticsRepository()


# ============================================================
# 5. LIST USERS TESTS
# ============================================================

def test_list_all_users(repo):

    result = ListAdminUsers(repo).execute(
        ListAdminUsersInput(
            actor=ADMIN,
        )
    )

    assert result.total == 3
    assert len(result.items) == 3
    assert result.limit == 20
    assert result.offset == 0


def test_list_users_filter_role(repo):

    result = ListAdminUsers(repo).execute(
        ListAdminUsersInput(
            actor=ADMIN,
            role=" UMKM ",
        )
    )

    assert result.total == 1
    assert result.items[0].id == "u1"

    assert (
        "count_users",
        "umkm",
        None,
    ) in repo.calls


def test_list_users_search(repo):

    result = ListAdminUsers(repo).execute(
        ListAdminUsersInput(
            actor=ADMIN,
            search="  FREELANCER  ",
        )
    )

    assert result.total == 1
    assert result.items[0].id == "f1"

    assert (
        "count_users",
        None,
        "FREELANCER",
    ) in repo.calls


def test_list_users_pagination(repo):

    result = ListAdminUsers(repo).execute(
        ListAdminUsersInput(
            actor=ADMIN,
            limit=1,
            offset=1,
        )
    )

    assert result.total == 3
    assert len(result.items) == 1
    assert result.items[0].id == "f1"


def test_list_users_no_match(repo):

    result = ListAdminUsers(repo).execute(
        ListAdminUsersInput(
            actor=ADMIN,
            search="tidak-ada",
        )
    )

    assert result.total == 0
    assert result.items == ()


@pytest.mark.parametrize(
    "limit",
    [0, 101, True],
)
def test_list_users_invalid_limit(repo, limit):

    with pytest.raises(BadRequestError):
        ListAdminUsers(repo).execute(
            ListAdminUsersInput(
                actor=ADMIN,
                limit=limit,
            )
        )

    assert repo.calls == []


@pytest.mark.parametrize(
    "offset",
    [-1, 10001, True],
)
def test_list_users_invalid_offset(repo, offset):

    with pytest.raises(BadRequestError):
        ListAdminUsers(repo).execute(
            ListAdminUsersInput(
                actor=ADMIN,
                offset=offset,
            )
        )


@pytest.mark.parametrize(
    "role",
    ["admin", "guest"],
)
def test_list_users_invalid_role_filter(repo, role):

    with pytest.raises(BadRequestError):
        ListAdminUsers(repo).execute(
            ListAdminUsersInput(
                actor=ADMIN,
                role=role,
            )
        )


def test_list_users_invalid_search(repo):

    with pytest.raises(BadRequestError):
        ListAdminUsers(repo).execute(
            ListAdminUsersInput(
                actor=ADMIN,
                search="a" * 101,
            )
        )


def test_list_users_invalid_count(repo):

    repo.override_user_count = -1

    with pytest.raises(ConflictError):
        ListAdminUsers(repo).execute(
            ListAdminUsersInput(actor=ADMIN)
        )


def test_list_users_boolean_count_rejected(repo):

    repo.override_user_count = True

    with pytest.raises(ConflictError):
        ListAdminUsers(repo).execute(
            ListAdminUsersInput(actor=ADMIN)
        )


def test_list_users_wrong_role_result(repo):

    repo.override_users = (
        repo.users[1],
    )

    with pytest.raises(ConflictError):
        ListAdminUsers(repo).execute(
            ListAdminUsersInput(
                actor=ADMIN,
                role="umkm",
            )
        )


def test_list_users_too_many_results(repo):

    repo.override_users = (
        repo.users[0],
        repo.users[1],
    )

    with pytest.raises(ConflictError):
        ListAdminUsers(repo).execute(
            ListAdminUsersInput(
                actor=ADMIN,
                limit=1,
            )
        )


def test_list_users_invalid_row(repo):

    repo.override_users = (
        {"id": "u1"},
    )

    with pytest.raises(ConflictError):
        ListAdminUsers(repo).execute(
            ListAdminUsersInput(actor=ADMIN)
        )


# ============================================================
# 6. USER DETAIL TESTS
# ============================================================

def test_get_umkm_detail(repo):

    result = GetAdminUser(repo).execute(
        GetAdminUserInput(
            actor=ADMIN,
            user_id="u1",
        )
    )

    assert result.user.role == "umkm"
    assert result.umkm_profile is not None
    assert result.freelancer_profile is None


def test_get_freelancer_detail(repo):

    result = GetAdminUser(repo).execute(
        GetAdminUserInput(
            actor=ADMIN,
            user_id="f1",
        )
    )

    assert result.user.role == "freelancer"
    assert result.freelancer_profile is not None
    assert result.umkm_profile is None


def test_get_admin_user_without_profile(repo):

    result = GetAdminUser(repo).execute(
        GetAdminUserInput(
            actor=ADMIN,
            user_id="a1",
        )
    )

    assert result.user.role == "admin"
    assert result.umkm_profile is None
    assert result.freelancer_profile is None


def test_get_missing_user(repo):

    with pytest.raises(NotFoundError):
        GetAdminUser(repo).execute(
            GetAdminUserInput(
                actor=ADMIN,
                user_id="missing",
            )
        )


def test_get_user_invalid_id(repo):

    with pytest.raises(BadRequestError):
        GetAdminUser(repo).execute(
            GetAdminUserInput(
                actor=ADMIN,
                user_id="  ",
            )
        )


def test_get_user_wrong_repository_identity(repo):

    repo.override_user_detail = (
        repo.user_details["f1"]
    )

    with pytest.raises(ConflictError):
        GetAdminUser(repo).execute(
            GetAdminUserInput(
                actor=ADMIN,
                user_id="u1",
            )
        )


def test_get_user_wrong_profile_role(repo):

    repo.override_user_detail = AdminUserDetail(
        user=repo.users[0],
        freelancer_profile=(
            repo.user_details["f1"].freelancer_profile
        ),
    )

    with pytest.raises(ConflictError):
        GetAdminUser(repo).execute(
            GetAdminUserInput(
                actor=ADMIN,
                user_id="u1",
            )
        )


# ============================================================
# 7. LIST PROJECTS TESTS
# ============================================================

def test_list_all_projects(repo):

    result = ListAdminProjects(repo).execute(
        ListAdminProjectsInput(
            actor=ADMIN,
        )
    )

    assert result.total == 2
    assert len(result.items) == 2


def test_list_project_filter_status(repo):

    result = ListAdminProjects(repo).execute(
        ListAdminProjectsInput(
            actor=ADMIN,
            status=" selesai ",
        )
    )

    assert result.total == 1
    assert result.items[0].id == "p2"

    assert (
        "count_projects",
        "SELESAI",
        None,
    ) in repo.calls


def test_list_project_search(repo):

    result = ListAdminProjects(repo).execute(
        ListAdminProjectsInput(
            actor=ADMIN,
            search="  logo ",
        )
    )

    assert result.total == 1
    assert result.items[0].title == "Desain Logo"


def test_list_project_without_freelancer(repo):

    result = ListAdminProjects(repo).execute(
        ListAdminProjectsInput(
            actor=ADMIN,
            status="TERBUKA",
        )
    )

    assert result.items[0].assigned_freelancer_id is None


def test_list_project_no_match(repo):

    result = ListAdminProjects(repo).execute(
        ListAdminProjectsInput(
            actor=ADMIN,
            search="tidak-ada",
        )
    )

    assert result.total == 0
    assert result.items == ()


def test_list_project_invalid_status(repo):

    with pytest.raises(BadRequestError):
        ListAdminProjects(repo).execute(
            ListAdminProjectsInput(
                actor=ADMIN,
                status="DROP;TABLE",
            )
        )


@pytest.mark.parametrize(
    "limit",
    [0, 101, True],
)
def test_list_project_invalid_limit(repo, limit):

    with pytest.raises(BadRequestError):
        ListAdminProjects(repo).execute(
            ListAdminProjectsInput(
                actor=ADMIN,
                limit=limit,
            )
        )


def test_list_project_invalid_offset(repo):

    with pytest.raises(BadRequestError):
        ListAdminProjects(repo).execute(
            ListAdminProjectsInput(
                actor=ADMIN,
                offset=-1,
            )
        )


def test_list_project_invalid_count(repo):

    repo.override_project_count = -1

    with pytest.raises(ConflictError):
        ListAdminProjects(repo).execute(
            ListAdminProjectsInput(actor=ADMIN)
        )


def test_list_project_wrong_status_result(repo):

    repo.override_projects = (
        repo.projects[0],
    )

    with pytest.raises(ConflictError):
        ListAdminProjects(repo).execute(
            ListAdminProjectsInput(
                actor=ADMIN,
                status="SELESAI",
            )
        )


def test_list_project_too_many_results(repo):

    repo.override_projects = repo.projects

    with pytest.raises(ConflictError):
        ListAdminProjects(repo).execute(
            ListAdminProjectsInput(
                actor=ADMIN,
                limit=1,
            )
        )


# ============================================================
# 8. PROJECT DETAIL TESTS
# ============================================================

def test_get_project_without_agreement(repo):

    result = GetAdminProject(repo).execute(
        GetAdminProjectInput(
            actor=ADMIN,
            project_id="p1",
        )
    )

    assert result.project.id == "p1"
    assert result.agreed_price is None
    assert result.project.assigned_freelancer_id is None


def test_get_project_with_agreement(repo):

    result = GetAdminProject(repo).execute(
        GetAdminProjectInput(
            actor=ADMIN,
            project_id="p2",
        )
    )

    assert result.project.id == "p2"
    assert result.agreed_price == 1800000
    assert result.project.assigned_freelancer_id == "f1"


def test_get_missing_project(repo):

    with pytest.raises(NotFoundError):
        GetAdminProject(repo).execute(
            GetAdminProjectInput(
                actor=ADMIN,
                project_id="missing",
            )
        )


def test_get_project_invalid_id(repo):

    with pytest.raises(BadRequestError):
        GetAdminProject(repo).execute(
            GetAdminProjectInput(
                actor=ADMIN,
                project_id="",
            )
        )


def test_get_project_wrong_identity(repo):

    repo.override_project_detail = (
        repo.project_details["p2"]
    )

    with pytest.raises(ConflictError):
        GetAdminProject(repo).execute(
            GetAdminProjectInput(
                actor=ADMIN,
                project_id="p1",
            )
        )


def test_get_project_invalid_result_type(repo):

    repo.override_project_detail = {
        "project_id": "p1"
    }

    with pytest.raises(ConflictError):
        GetAdminProject(repo).execute(
            GetAdminProjectInput(
                actor=ADMIN,
                project_id="p1",
            )
        )


# ============================================================
# 9. SYSTEM STATISTICS TESTS
# ============================================================

def test_get_system_statistics(repo):

    result = GetAdminStatistics(repo).execute(
        GetAdminStatisticsInput(
            actor=ADMIN,
        )
    )

    assert result.total_umkm == 1
    assert result.total_freelancers == 1
    assert result.total_projects == 2
    assert result.completed_projects == 1
    assert result.total_transactions == 3
    assert result.platform_income == 90000


def test_get_system_statistics_zero_values(repo):

    repo.statistics = AdminSystemStatistics(
        total_umkm=0,
        total_freelancers=0,
        total_projects=0,
        completed_projects=0,
        total_transactions=0,
        platform_income=0,
    )

    result = GetAdminStatistics(repo).execute(
        GetAdminStatisticsInput(
            actor=ADMIN,
        )
    )

    assert result.total_projects == 0
    assert result.platform_income == 0


def test_get_statistics_invalid_completed_count(repo):

    repo.statistics = replace(
        repo.statistics,
        total_projects=1,
        completed_projects=2,
    )

    with pytest.raises(ConflictError):
        GetAdminStatistics(repo).execute(
            GetAdminStatisticsInput(
                actor=ADMIN,
            )
        )


def test_get_statistics_negative_income(repo):

    repo.statistics = replace(
        repo.statistics,
        platform_income=-1,
    )

    with pytest.raises(ConflictError):
        GetAdminStatistics(repo).execute(
            GetAdminStatisticsInput(
                actor=ADMIN,
            )
        )


def test_get_statistics_wrong_result_type(repo):

    repo.override_statistics = {
        "total_umkm": 1
    }

    with pytest.raises(ConflictError):
        GetAdminStatistics(repo).execute(
            GetAdminStatisticsInput(
                actor=ADMIN,
            )
        )


# ============================================================
# 10. ADMIN AUTHORIZATION TESTS
# ============================================================

@pytest.mark.parametrize(
    "actor",
    [
        UMKM_ACTOR,
        FREELANCER_ACTOR,
        AdminActor("guest1", "guest"),
        AdminActor("", "admin"),
    ],
)
@pytest.mark.parametrize(
    "use_case",
    [
        "list_users",
        "get_user",
        "list_projects",
        "get_project",
        "statistics",
    ],
)
def test_non_admin_rejected_for_all_use_cases(
    repo,
    actor,
    use_case,
):

    if use_case == "list_users":

        action = lambda: ListAdminUsers(repo).execute(
            ListAdminUsersInput(actor=actor)
        )

    elif use_case == "get_user":

        action = lambda: GetAdminUser(repo).execute(
            GetAdminUserInput(
                actor=actor,
                user_id="u1",
            )
        )

    elif use_case == "list_projects":

        action = lambda: ListAdminProjects(repo).execute(
            ListAdminProjectsInput(actor=actor)
        )

    elif use_case == "get_project":

        action = lambda: GetAdminProject(repo).execute(
            GetAdminProjectInput(
                actor=actor,
                project_id="p1",
            )
        )

    else:

        action = lambda: GetAdminStatistics(repo).execute(
            GetAdminStatisticsInput(actor=actor)
        )

    with pytest.raises(ForbiddenError):
        action()

    # Authorization harus terjadi
    # sebelum Repository diakses.
    assert repo.calls == []