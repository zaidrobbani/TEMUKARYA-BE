
from uuid import uuid4

import pytest

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)

from app.modules.applications.application.dto import (
    SubmitApplicationInput,
)

from app.modules.applications.application.use_cases import (
    GetMyApplications,
    GetProjectApplicants,
    SubmitApplication,
)

from app.modules.applications.domain.entities import (
    ProjectApplication,
)


# ============================================================
# TEST IDENTIFIERS
# ============================================================

FREELANCER_ID = "11111111-1111-4111-8111-111111111111"
UMKM_ID = "22222222-2222-4222-8222-222222222222"
PROJECT_ID = "33333333-3333-4333-8333-333333333333"


# ============================================================
# FAKE REPOSITORY
# ============================================================

class FakeApplicationRepository:

    def __init__(self):
        self.applications = []
        self.profile_exists = True
        self.open_project = True
        self.project_owner_id = UMKM_ID

        self.project_lock_requested = False
        self.last_list_freelancer = None
        self.last_list_project = None

    def freelancer_profile_exists(
        self,
        freelancer_id,
    ):
        return self.profile_exists

    def project_is_open(
        self,
        project_id,
        lock=False,
    ):
        self.project_lock_requested = lock
        return self.open_project

    def project_owned_by_umkm(
        self,
        project_id,
        umkm_id,
    ):
        return (
            project_id == PROJECT_ID
            and umkm_id == self.project_owner_id
        )

    def add(self, application):
        self.applications.append(application)
        return application

    def get_by_id(self, application_id):
        return next(
            (
                item
                for item in self.applications
                if item.id == application_id
            ),
            None,
        )

    def get_by_project_and_freelancer(
        self,
        project_id,
        freelancer_id,
    ):
        return next(
            (
                item
                for item in self.applications
                if item.project_id == project_id
                and item.freelancer_id == freelancer_id
            ),
            None,
        )

    def list_by_freelancer(
        self,
        freelancer_id,
        limit,
        offset,
    ):
        self.last_list_freelancer = (
            freelancer_id,
            limit,
            offset,
        )

        matching = [
            item
            for item in self.applications
            if item.freelancer_id == freelancer_id
        ]

        return matching[offset:offset + limit]

    def list_by_project(
        self,
        project_id,
        limit,
        offset,
    ):
        self.last_list_project = (
            project_id,
            limit,
            offset,
        )

        matching = [
            item
            for item in self.applications
            if item.project_id == project_id
        ]

        return matching[offset:offset + limit]


# ============================================================
# FAKE UNIT OF WORK
# ============================================================

class FakeUnitOfWork:

    def __init__(self):
        self.commit_count = 0

    def commit(self):
        self.commit_count += 1


# ============================================================
# FIXTURE
# ============================================================

@pytest.fixture
def context():

    repository = FakeApplicationRepository()
    uow = FakeUnitOfWork()

    submit = SubmitApplication(
        repository=repository,
        uow=uow,
    )

    return repository, uow, submit


# ============================================================
# TEST DATA FACTORIES
# ============================================================

def valid_input():
    return SubmitApplicationInput(
        proposed_price=1500000,
        estimated_duration_days=14,
        proposal_message=(
            "Saya berpengalaman membuat website UMKM."
        ),
    )


def make_application(
    freelancer_id=FREELANCER_ID,
    project_id=PROJECT_ID,
):
    return ProjectApplication(
        id=str(uuid4()),
        freelancer_id=freelancer_id,
        project_id=project_id,
        proposed_price=1500000,
        estimated_duration_days=14,
        proposal_message="Proposal proyek UMKM",
    )


# ============================================================
# SUBMIT APPLICATION TESTS
# ============================================================

def test_submit_application_success(context):
    repository, uow, submit = context

    result = submit.execute(
        freelancer_id=FREELANCER_ID,
        project_id=PROJECT_ID,
        data=valid_input(),
    )

    assert result.project_id == PROJECT_ID
    assert result.freelancer_id == FREELANCER_ID

    assert result.proposed_price == 1500000
    assert result.estimated_duration_days == 14

    assert result.status == "SUBMITTED"
    assert len(repository.applications) == 1

    assert repository.project_lock_requested is True
    assert uow.commit_count == 1


def test_submit_trims_proposal_message(context):
    repository, uow, submit = context

    data = SubmitApplicationInput(
        proposed_price=100000,
        estimated_duration_days=3,
        proposal_message="  Saya siap mengerjakan.  ",
    )

    result = submit.execute(
        FREELANCER_ID,
        PROJECT_ID,
        data,
    )

    assert result.proposal_message == (
        "Saya siap mengerjakan."
    )


@pytest.mark.parametrize(
    "price",
    [
        0,
        -100,
        True,
        1.5,
        2**64,
    ],
)
def test_submit_rejects_invalid_price(
    context,
    price,
):
    repository, uow, submit = context

    data = SubmitApplicationInput(
        proposed_price=price,
        estimated_duration_days=14,
        proposal_message="Proposal valid",
    )

    with pytest.raises(BadRequestError):
        submit.execute(
            FREELANCER_ID,
            PROJECT_ID,
            data,
        )

    assert repository.applications == []
    assert uow.commit_count == 0


@pytest.mark.parametrize(
    "duration",
    [
        0,
        -5,
        True,
        1.5,
        2**32,
    ],
)
def test_submit_rejects_invalid_duration(
    context,
    duration,
):
    repository, uow, submit = context

    data = SubmitApplicationInput(
        proposed_price=100000,
        estimated_duration_days=duration,
        proposal_message="Proposal valid",
    )

    with pytest.raises(BadRequestError):
        submit.execute(
            FREELANCER_ID,
            PROJECT_ID,
            data,
        )

    assert repository.applications == []
    assert uow.commit_count == 0


@pytest.mark.parametrize(
    "message",
    [
        "",
        " ",
        "\n\t",
        "x" * 5001,
        None,
    ],
)
def test_submit_rejects_invalid_message(
    context,
    message,
):
    repository, uow, submit = context

    data = SubmitApplicationInput(
        proposed_price=100000,
        estimated_duration_days=5,
        proposal_message=message,
    )

    with pytest.raises(BadRequestError):
        submit.execute(
            FREELANCER_ID,
            PROJECT_ID,
            data,
        )

    assert repository.applications == []
    assert uow.commit_count == 0


def test_submit_requires_freelancer_profile(context):
    repository, uow, submit = context

    repository.profile_exists = False

    with pytest.raises(NotFoundError):
        submit.execute(
            FREELANCER_ID,
            PROJECT_ID,
            valid_input(),
        )

    assert repository.applications == []
    assert uow.commit_count == 0


def test_submit_rejects_closed_project(context):
    repository, uow, submit = context

    repository.open_project = False

    with pytest.raises(NotFoundError):
        submit.execute(
            FREELANCER_ID,
            PROJECT_ID,
            valid_input(),
        )

    assert repository.applications == []
    assert uow.commit_count == 0


def test_submit_rejects_duplicate_application(context):
    repository, uow, submit = context

    repository.applications.append(
        make_application()
    )

    with pytest.raises(ConflictError):
        submit.execute(
            FREELANCER_ID,
            PROJECT_ID,
            valid_input(),
        )

    assert len(repository.applications) == 1
    assert uow.commit_count == 0


# ============================================================
# GET MY APPLICATIONS TESTS
# ============================================================

def test_get_my_applications(context):
    repository, uow, submit = context

    repository.applications = [
        make_application(),
        make_application(),
        make_application(
            freelancer_id="other-freelancer"
        ),
    ]

    use_case = GetMyApplications(repository)

    page = use_case.execute(
        freelancer_id=FREELANCER_ID,
        limit=10,
        offset=0,
    )

    assert len(page.items) == 2
    assert page.has_more is False
    assert page.limit == 10
    assert page.offset == 0

    assert all(
        item.freelancer_id == FREELANCER_ID
        for item in page.items
    )

    assert repository.last_list_freelancer == (
        FREELANCER_ID,
        11,
        0,
    )


def test_get_my_applications_pagination(context):
    repository, uow, submit = context

    repository.applications = [
        make_application()
        for _ in range(5)
    ]

    use_case = GetMyApplications(repository)

    first_page = use_case.execute(
        freelancer_id=FREELANCER_ID,
        limit=2,
        offset=0,
    )

    second_page = use_case.execute(
        freelancer_id=FREELANCER_ID,
        limit=2,
        offset=2,
    )

    assert len(first_page.items) == 2
    assert first_page.has_more is True

    assert len(second_page.items) == 2
    assert second_page.has_more is True


@pytest.mark.parametrize(
    "limit,offset",
    [
        (0, 0),
        (101, 0),
        (10, -1),
        (True, 0),
        (10, False),
    ],
)
def test_get_my_applications_invalid_pagination(
    context,
    limit,
    offset,
):
    repository, uow, submit = context

    use_case = GetMyApplications(repository)

    with pytest.raises(BadRequestError):
        use_case.execute(
            freelancer_id=FREELANCER_ID,
            limit=limit,
            offset=offset,
        )


# ============================================================
# GET PROJECT APPLICANTS TESTS
# ============================================================

def test_umkm_can_view_project_applicants(context):
    repository, uow, submit = context

    repository.applications = [
        make_application(),
        make_application(
            freelancer_id="freelancer-2"
        ),
    ]

    use_case = GetProjectApplicants(repository)

    page = use_case.execute(
        umkm_id=UMKM_ID,
        project_id=PROJECT_ID,
        limit=10,
        offset=0,
    )

    assert len(page.items) == 2
    assert page.has_more is False

    assert repository.last_list_project == (
        PROJECT_ID,
        11,
        0,
    )


def test_other_umkm_cannot_view_applicants(context):
    repository, uow, submit = context

    repository.applications = [
        make_application()
    ]

    use_case = GetProjectApplicants(repository)

    with pytest.raises(NotFoundError):
        use_case.execute(
            umkm_id="other-umkm",
            project_id=PROJECT_ID,
        )

    assert repository.last_list_project is None


def test_missing_project_cannot_view_applicants(context):
    repository, uow, submit = context

    use_case = GetProjectApplicants(repository)

    with pytest.raises(NotFoundError):
        use_case.execute(
            umkm_id=UMKM_ID,
            project_id="missing-project",
        )

    assert repository.last_list_project is None


def test_project_applicants_pagination(context):
    repository, uow, submit = context

    repository.applications = [
        make_application(
            freelancer_id=f"freelancer-{i}"
        )
        for i in range(5)
    ]

    use_case = GetProjectApplicants(repository)

    page = use_case.execute(
        umkm_id=UMKM_ID,
        project_id=PROJECT_ID,
        limit=2,
        offset=0,
    )

    assert len(page.items) == 2
    assert page.has_more is True


@pytest.mark.parametrize(
    "limit,offset",
    [
        (0, 0),
        (101, 0),
        (10, -1),
        (True, 0),
    ],
)
def test_project_applicants_invalid_pagination(
    context,
    limit,
    offset,
):
    repository, uow, submit = context

    use_case = GetProjectApplicants(repository)

    with pytest.raises(BadRequestError):
        use_case.execute(
            umkm_id=UMKM_ID,
            project_id=PROJECT_ID,
            limit=limit,
            offset=offset,
        )
