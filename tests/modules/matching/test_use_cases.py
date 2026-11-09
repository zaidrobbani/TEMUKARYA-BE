
import pytest

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)

from app.modules.matching.application.dto import (
    RecommendFreelancersInput,
    RecommendProjectsInput,
)

from app.modules.matching.application.use_cases import (
    RecommendFreelancersForProject,
    RecommendProjectsForFreelancer,
)

from app.modules.matching.domain.entities import (
    FreelancerMatchingSource,
    ProjectMatchingSource,
)


# ============================================================
# TEST CONSTANTS
# ============================================================

REQUIRED = (
    "python",
    "fastapi",
    "mysql",
    "docker",
    "react",
)


# ============================================================
# TEST DATA FACTORIES
# ============================================================

def project(
    project_id="p1",
    required=REQUIRED,
    owner="u1",
    status="TERBUKA",
    title="Website",
):
    return ProjectMatchingSource(
        project_id=project_id,
        umkm_id=owner,
        title=title,
        category_id="website",
        status=status,
        required_skill_ids=required,
    )


def freelancer(
    freelancer_id="f1",
    skills=REQUIRED,
    name="Andi",
    status="AVAILABLE",
):
    return FreelancerMatchingSource(
        freelancer_id=freelancer_id,
        name=name,
        professional_title="Developer",
        city="Malang",
        availability_status=status,
        skill_ids=skills,
    )


# ============================================================
# FAKE MATCHING REPOSITORY
# ============================================================

class FakeMatchingRepository:

    def __init__(self):

        self.projects = {
            "p1": project(),
        }

        self.freelancers = {
            "f1": freelancer(),
        }

        self.available_candidates = [
            freelancer(
                "f2",
                REQUIRED[:3],
                name="Budi",
            ),
            freelancer(
                "f1",
                REQUIRED,
                name="Andi",
            ),
            freelancer(
                "f3",
                REQUIRED[:2],
                name="Cici",
            ),
            freelancer(
                "f4",
                REQUIRED,
                name="Dina",
                status="BUSY",
            ),
            freelancer(
                "f5",
                REQUIRED[:3],
                name="Ayu",
            ),
        ]

        self.published_candidates = [
            project(
                "p2",
                REQUIRED[:3],
                title="B Project",
            ),
            project(
                "p3",
                ("rust", "go"),
                title="No Match",
            ),
            project(
                "p1",
                REQUIRED[:5],
                title="Top Project",
            ),
            project(
                "p4",
                REQUIRED[:3],
                status="DRAFT",
                title="Closed",
            ),
            project(
                "p5",
                (),
                title="Empty",
            ),
            project(
                "p6",
                REQUIRED[:3],
                title="A Project",
            ),
        ]

        self.available_calls = 0
        self.published_calls = 0

    def get_project(
        self,
        project_id,
    ):
        return self.projects.get(project_id)

    def get_freelancer(
        self,
        freelancer_id,
    ):
        return self.freelancers.get(
            freelancer_id
        )

    def iter_available_freelancers(self):
        self.available_calls += 1
        return iter(
            self.available_candidates
        )

    def iter_published_projects(self):
        self.published_calls += 1
        return iter(
            self.published_candidates
        )


# ============================================================
# FIXTURE
# ============================================================

@pytest.fixture
def context():

    repo = FakeMatchingRepository()

    return (
        repo,
        RecommendFreelancersForProject(repo),
        RecommendProjectsForFreelancer(repo),
    )


# ============================================================
# 1. FREELANCER RECOMMENDATIONS
# ============================================================

def test_freelancer_recommendations_sort_and_threshold(
    context,
):
    repo, recommend, _ = context

    result = recommend.execute(
        RecommendFreelancersInput(
            "p1",
            "u1",
        )
    )

    assert [
        x.freelancer.freelancer_id
        for x in result.items
    ] == [
        "f1",
        "f5",
        "f2",
    ]

    assert [
        x.match.score_percent
        for x in result.items
    ] == [
        100.0,
        60.0,
        60.0,
    ]

    assert result.has_more is False


def test_freelancer_recommendations_explain_match(
    context,
):
    _, recommend, _ = context

    items = recommend.execute(
        RecommendFreelancersInput(
            "p1",
            "u1",
        )
    ).items

    assert (
        items[1].match.matched_skill_ids
        == REQUIRED[:3]
    )

    assert (
        items[1].match.missing_skill_ids
        == REQUIRED[3:]
    )


# ============================================================
# 2. FREELANCER PAGINATION
# ============================================================

def test_freelancer_pagination(context):
    repo, recommend, _ = context

    result = recommend.execute(
        RecommendFreelancersInput(
            "p1",
            "u1",
            limit=2,
            offset=0,
        )
    )

    assert len(result.items) == 2
    assert result.has_more is True

    result = recommend.execute(
        RecommendFreelancersInput(
            "p1",
            "u1",
            limit=2,
            offset=2,
        )
    )

    assert [
        x.freelancer.freelancer_id
        for x in result.items
    ] == ["f2"]

    assert result.has_more is False


# ============================================================
# 3. OWNERSHIP AND NOT FOUND
# ============================================================

def test_freelancer_nonowner_and_notfound_same_error(
    context,
):
    repo, recommend, _ = context

    with pytest.raises(
        NotFoundError
    ) as forbidden:

        recommend.execute(
            RecommendFreelancersInput(
                "p1",
                "other",
            )
        )

    with pytest.raises(
        NotFoundError
    ) as absent:

        recommend.execute(
            RecommendFreelancersInput(
                "missing",
                "u1",
            )
        )

    assert (
        forbidden.value.message
        == absent.value.message
    )

    assert repo.available_calls == 0


# ============================================================
# 4. PROJECT STATUS
# ============================================================

def test_freelancer_closed_project_conflict(
    context,
):
    repo, recommend, _ = context

    repo.projects["p1"] = project(
        status="DRAFT"
    )

    with pytest.raises(ConflictError):
        recommend.execute(
            RecommendFreelancersInput(
                "p1",
                "u1",
            )
        )

    assert repo.available_calls == 0


# ============================================================
# 5. EMPTY PROJECT SKILLS
# ============================================================

def test_freelancer_empty_required_skills(
    context,
):
    repo, recommend, _ = context

    repo.projects["p1"] = project(
        required=()
    )

    result = recommend.execute(
        RecommendFreelancersInput(
            "p1",
            "u1",
        )
    )

    assert result.items == ()
    assert repo.available_calls == 0


# ============================================================
# 6. EMPTY CANDIDATES
# ============================================================

def test_freelancer_empty_eligible_candidates(
    context,
):
    repo, recommend, _ = context

    repo.available_candidates = []

    result = recommend.execute(
        RecommendFreelancersInput(
            "p1",
            "u1",
        )
    )

    assert result.items == ()
    assert not result.has_more


# ============================================================
# 7. DUPLICATE FREELANCERS
# ============================================================

def test_freelancer_duplicate_candidate_ids(
    context,
):
    repo, recommend, _ = context

    repo.available_candidates.append(
        freelancer(
            "f1",
            REQUIRED,
        )
    )

    items = recommend.execute(
        RecommendFreelancersInput(
            "p1",
            "u1",
        )
    ).items

    ids = [
        x.freelancer.freelancer_id
        for x in items
    ]

    assert len(ids) == len(set(ids))


# ============================================================
# 8. NORMALIZE PROJECT AND UMKM IDS
# ============================================================

def test_freelancer_trims_user_and_project_ids(
    context,
):
    repo, recommend, _ = context

    page = recommend.execute(
        RecommendFreelancersInput(
            " p1 ",
            " u1 ",
        )
    )

    assert page.project_id == "p1"


# ============================================================
# 9. PROJECT RECOMMENDATIONS
# ============================================================

def test_project_recommendations_sort_and_threshold(
    context,
):
    repo, _, recommend = context

    result = recommend.execute(
        RecommendProjectsInput("f1")
    )

    assert [
        x.project.project_id
        for x in result.items
    ] == [
        "p1",
        "p6",
        "p2",
    ]

    assert [
        x.match.score_percent
        for x in result.items
    ] == [
        100.0,
        100.0,
        100.0,
    ]


# ============================================================
# 10. PROJECT SCORE THRESHOLD
# ============================================================

def test_project_recommendations_score_60_percent(
    context,
):
    repo, _, recommend = context

    repo.freelancers["f1"] = freelancer(
        skills=REQUIRED[:3]
    )

    result = recommend.execute(
        RecommendProjectsInput("f1")
    )

    assert [
        x.project.project_id
        for x in result.items
    ] == [
        "p6",
        "p2",
        "p1",
    ]

    assert [
        x.match.score_percent
        for x in result.items
    ] == [
        100.0,
        100.0,
        60.0,
    ]


# ============================================================
# 11. PROJECT PAGINATION
# ============================================================

def test_project_pagination(context):
    _, _, recommend = context

    result = recommend.execute(
        RecommendProjectsInput(
            "f1",
            limit=2,
        )
    )

    assert [
        x.project.project_id
        for x in result.items
    ] == [
        "p1",
        "p6",
    ]

    assert result.has_more is True

    next_page = recommend.execute(
        RecommendProjectsInput(
            "f1",
            limit=2,
            offset=2,
        )
    )

    assert [
        x.project.project_id
        for x in next_page.items
    ] == ["p2"]

    assert next_page.has_more is False


# ============================================================
# 12. FREELANCER NOT FOUND
# ============================================================

def test_project_freelancer_notfound(
    context,
):
    repo, _, recommend = context

    with pytest.raises(NotFoundError):
        recommend.execute(
            RecommendProjectsInput(
                "unknown"
            )
        )

    assert repo.published_calls == 0


# ============================================================
# 13. FREELANCER WITHOUT SKILLS
# ============================================================

def test_project_freelancer_without_skills(
    context,
):
    repo, _, recommend = context

    repo.freelancers["f1"] = freelancer(
        skills=()
    )

    result = recommend.execute(
        RecommendProjectsInput("f1")
    )

    assert result.items == ()
    assert repo.published_calls == 0


# ============================================================
# 14. BUSY FREELANCER CAN BROWSE PROJECTS
# ============================================================

def test_busy_freelancer_can_browse_projects(
    context,
):
    repo, _, recommend = context

    repo.freelancers["f1"] = freelancer(
        status="BUSY"
    )

    assert recommend.execute(
        RecommendProjectsInput("f1")
    ).items


# ============================================================
# 15. STALE AND EMPTY PROJECTS EXCLUDED
# ============================================================

def test_projects_stale_or_empty_skills_excluded(
    context,
):
    repo, _, recommend = context

    items = recommend.execute(
        RecommendProjectsInput("f1")
    ).items

    ids = [
        x.project.project_id
        for x in items
    ]

    assert "p4" not in ids
    assert "p5" not in ids


# ============================================================
# 16. DUPLICATE PROJECTS
# ============================================================

def test_projects_duplicate_candidates_excluded(
    context,
):
    repo, _, recommend = context

    repo.published_candidates.append(
        project(
            "p1",
            REQUIRED,
        )
    )

    ids = [
        x.project.project_id
        for x in recommend.execute(
            RecommendProjectsInput("f1")
        ).items
    ]

    assert len(ids) == len(set(ids))


# ============================================================
# 17. NORMALIZE FREELANCER ID
# ============================================================

def test_project_recommendations_trims_identity(
    context,
):
    _, _, recommend = context

    result = recommend.execute(
        RecommendProjectsInput(" f1 ")
    )

    assert result.freelancer_id == "f1"


# ============================================================
# 18. INVALID PAGINATION
# ============================================================

@pytest.mark.parametrize(
    "limit,offset",
    [
        (0, 0),
        (101, 0),
        (True, 0),
        (20, -1),
        (20, 10001),
        (20, False),
    ],
)
def test_invalid_pagination_for_both_use_cases(
    context,
    limit,
    offset,
):
    repo, umkm, freelancer_uc = context

    with pytest.raises(BadRequestError):
        umkm.execute(
            RecommendFreelancersInput(
                "p1",
                "u1",
                limit=limit,
                offset=offset,
            )
        )

    with pytest.raises(BadRequestError):
        freelancer_uc.execute(
            RecommendProjectsInput(
                "f1",
                limit=limit,
                offset=offset,
            )
        )

    assert (
        repo.available_calls
        == repo.published_calls
        == 0
    )


# ============================================================
# 19. INVALID IDS
# ============================================================

@pytest.mark.parametrize(
    "bad_id",
    [
        "",
        "   ",
        None,
        123,
        "x" * 37,
    ],
)
def test_invalid_identity_for_both_use_cases(
    context,
    bad_id,
):
    _, umkm, freelancer_uc = context

    with pytest.raises(BadRequestError):
        umkm.execute(
            RecommendFreelancersInput(
                bad_id,
                "u1",
            )
        )

    with pytest.raises(BadRequestError):
        umkm.execute(
            RecommendFreelancersInput(
                "p1",
                bad_id,
            )
        )

    with pytest.raises(BadRequestError):
        freelancer_uc.execute(
            RecommendProjectsInput(
                bad_id
            )
        )