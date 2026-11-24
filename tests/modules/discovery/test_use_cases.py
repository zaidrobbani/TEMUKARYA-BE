
import pytest

from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
)

from app.modules.discovery.application.dto import (
    SearchFreelancersInput,
)

from app.modules.discovery.application.use_cases import (
    GetFreelancerDetail,
    SearchFreelancers,
)

from app.modules.discovery.domain.entities import (
    FreelancerDetail,
    FreelancerSearchFilters,
    FreelancerSummary,
)


# ============================================================
# TEST DATA
# ============================================================

FREELANCER_ID = (
    "11111111-1111-4111-8111-111111111111"
)


def make_freelancer(number=1):
    return FreelancerSummary(
        user_id=f"freelancer-{number}",
        name=f"Freelancer {number}",
        professional_title="Web Developer",
        city="Malang",
        availability_status="AVAILABLE",
    )


def make_detail():
    return FreelancerDetail(
        user_id=FREELANCER_ID,
        name="Andi",
        professional_title="Web Developer",
        city="Malang",
        availability_status="AVAILABLE",
        bio="Backend Developer",
    )


# ============================================================
# FAKE REPOSITORY
# ============================================================

class FakeDiscoveryRepository:

    def __init__(self):
        self.freelancers = []
        self.detail = make_detail()

        self.last_filters = None
        self.last_limit = None
        self.last_offset = None
        self.last_detail_id = None

    def search_freelancers(
        self,
        filters,
        limit,
        offset,
    ):
        self.last_filters = filters
        self.last_limit = limit
        self.last_offset = offset

        return self.freelancers[
            offset:offset + limit
        ]

    def get_freelancer_detail(
        self,
        freelancer_id,
    ):
        self.last_detail_id = freelancer_id
        return self.detail


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def context():
    repository = FakeDiscoveryRepository()

    search = SearchFreelancers(
        repository=repository
    )

    detail = GetFreelancerDetail(
        repository=repository
    )

    return repository, search, detail


# ============================================================
# SEARCH FREELANCERS
# ============================================================

def test_search_freelancers_default(context):
    repository, search, detail = context

    repository.freelancers = [
        make_freelancer(1),
        make_freelancer(2),
    ]

    page = search.execute(
        SearchFreelancersInput()
    )

    assert len(page.items) == 2
    assert page.limit == 20
    assert page.offset == 0
    assert page.has_more is False

    assert isinstance(
        repository.last_filters,
        FreelancerSearchFilters,
    )

    assert (
        repository.last_filters.availability_status
        == "AVAILABLE"
    )

    # limit + 1 untuk cek halaman berikutnya
    assert repository.last_limit == 21
    assert repository.last_offset == 0


def test_search_normalizes_text(context):
    repository, search, detail = context

    search.execute(
        SearchFreelancersInput(
            search="  backend  ",
            city="  Malang  ",
            availability_status=" AVAILABLE ",
        )
    )

    filters = repository.last_filters

    assert filters.search == "backend"
    assert filters.city == "Malang"
    assert filters.availability_status == "AVAILABLE"


def test_search_removes_duplicate_skill_ids(context):
    repository, search, detail = context

    search.execute(
        SearchFreelancersInput(
            skill_ids=(
                "python",
                "python",
                " fastapi ",
            ),
        )
    )

    assert repository.last_filters.skill_ids == (
        "python",
        "fastapi",
    )


def test_search_passes_all_filters(context):
    repository, search, detail = context

    search.execute(
        SearchFreelancersInput(
            search="designer",
            skill_ids=("graphic-design",),
            city="Malang",
            availability_status="AVAILABLE",
            min_price=500000,
            max_price=2000000,
            min_experience_count=2,
            min_rating=4.5,
        )
    )

    filters = repository.last_filters

    assert filters.search == "designer"
    assert filters.skill_ids == ("graphic-design",)
    assert filters.min_price == 500000
    assert filters.max_price == 2000000
    assert filters.min_experience_count == 2
    assert filters.min_rating == 4.5


def test_search_can_include_all_availability(context):
    repository, search, detail = context

    search.execute(
        SearchFreelancersInput(
            availability_status=None,
        )
    )

    assert (
        repository.last_filters.availability_status
        is None
    )


# ============================================================
# PAGINATION
# ============================================================

def test_search_pagination(context):
    repository, search, detail = context

    repository.freelancers = [
        make_freelancer(i)
        for i in range(5)
    ]

    page = search.execute(
        SearchFreelancersInput(
            limit=2,
            offset=0,
        )
    )

    assert len(page.items) == 2
    assert page.has_more is True

    assert repository.last_limit == 3
    assert repository.last_offset == 0


def test_search_last_page(context):
    repository, search, detail = context

    repository.freelancers = [
        make_freelancer(i)
        for i in range(5)
    ]

    page = search.execute(
        SearchFreelancersInput(
            limit=2,
            offset=4,
        )
    )

    assert len(page.items) == 1
    assert page.has_more is False


@pytest.mark.parametrize(
    "limit,offset",
    [
        (0, 0),
        (101, 0),
        (True, 0),
        (10, -1),
        (10, 10001),
        (10, False),
    ],
)
def test_search_invalid_pagination(
    context,
    limit,
    offset,
):
    repository, search, detail = context

    with pytest.raises(BadRequestError):
        search.execute(
            SearchFreelancersInput(
                limit=limit,
                offset=offset,
            )
        )

    assert repository.last_filters is None


# ============================================================
# TEXT VALIDATION
# ============================================================

@pytest.mark.parametrize(
    "invalid_search",
    [
        "",
        "   ",
        "a" * 101,
        123,
    ],
)
def test_search_invalid_search_text(
    context,
    invalid_search,
):
    repository, search, detail = context

    with pytest.raises(BadRequestError):
        search.execute(
            SearchFreelancersInput(
                search=invalid_search,
            )
        )


@pytest.mark.parametrize(
    "invalid_city",
    [
        "",
        "   ",
        "M" * 101,
        42,
    ],
)
def test_search_invalid_city(
    context,
    invalid_city,
):
    repository, search, detail = context

    with pytest.raises(BadRequestError):
        search.execute(
            SearchFreelancersInput(
                city=invalid_city,
            )
        )


# ============================================================
# SKILL VALIDATION
# ============================================================

@pytest.mark.parametrize(
    "skill_ids",
    [
        ("",),
        (" ",),
        ("x" * 51,),
        (123,),
        ["python"],
        tuple("skill-" + str(i) for i in range(51)),
    ],
)
def test_search_invalid_skills(
    context,
    skill_ids,
):
    repository, search, detail = context

    with pytest.raises(BadRequestError):
        search.execute(
            SearchFreelancersInput(
                skill_ids=skill_ids,
            )
        )


# ============================================================
# PRICE FILTER VALIDATION
# ============================================================

@pytest.mark.parametrize(
    "price",
    [
        -1,
        True,
        1.5,
        2**64,
    ],
)
def test_search_invalid_min_price(
    context,
    price,
):
    repository, search, detail = context

    with pytest.raises(BadRequestError):
        search.execute(
            SearchFreelancersInput(
                min_price=price,
            )
        )


def test_search_invalid_price_range(context):
    repository, search, detail = context

    with pytest.raises(BadRequestError):
        search.execute(
            SearchFreelancersInput(
                min_price=2000000,
                max_price=500000,
            )
        )


def test_search_accepts_zero_price(context):
    repository, search, detail = context

    search.execute(
        SearchFreelancersInput(
            min_price=0,
            max_price=100000,
        )
    )

    assert repository.last_filters.min_price == 0


# ============================================================
# EXPERIENCE VALIDATION
# ============================================================

@pytest.mark.parametrize(
    "experience",
    [
        -1,
        True,
        2.5,
    ],
)
def test_search_invalid_experience_count(
    context,
    experience,
):
    repository, search, detail = context

    with pytest.raises(BadRequestError):
        search.execute(
            SearchFreelancersInput(
                min_experience_count=experience,
            )
        )


# ============================================================
# RATING VALIDATION
# ============================================================

@pytest.mark.parametrize(
    "rating",
    [
        -1,
        5.1,
        True,
        float("nan"),
        float("inf"),
        "4.5",
    ],
)
def test_search_invalid_rating(
    context,
    rating,
):
    repository, search, detail = context

    with pytest.raises(BadRequestError):
        search.execute(
            SearchFreelancersInput(
                min_rating=rating,
            )
        )


def test_search_accepts_valid_rating(context):
    repository, search, detail = context

    search.execute(
        SearchFreelancersInput(
            min_rating=4.5,
        )
    )

    assert repository.last_filters.min_rating == 4.5


# FREELANCER DETAIL
def test_get_freelancer_detail_success(context):
    repository, search, detail = context

    freelancer = detail.execute(
        FREELANCER_ID
    )

    assert freelancer.user_id == FREELANCER_ID
    assert freelancer.name == "Andi"
    assert freelancer.bio == "Backend Developer"

    assert repository.last_detail_id == FREELANCER_ID


def test_get_freelancer_detail_trims_id(context):
    repository, search, detail = context

    detail.execute(
        f"  {FREELANCER_ID}  "
    )

    assert repository.last_detail_id == FREELANCER_ID


def test_get_freelancer_detail_not_found(context):
    repository, search, detail = context

    repository.detail = None

    with pytest.raises(NotFoundError):
        detail.execute(FREELANCER_ID)


@pytest.mark.parametrize(
    "invalid_id",
    [
        "",
        "   ",
        "x" * 37,
        None,
        123,
    ],
)
def test_get_freelancer_detail_invalid_id(
    context,
    invalid_id,
):
    repository, search, detail = context

    with pytest.raises(BadRequestError):
        detail.execute(invalid_id)

    assert repository.last_detail_id is None