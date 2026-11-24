from dataclasses import replace
from datetime import datetime
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.unit_of_work import UnitOfWork
from app.modules.profiles.application.dto import CreatePortfolioInput, UpdatePortfolioInput
from app.modules.profiles.application.use_cases import (
    CreatePortfolio, GetPortfolios, GetPortfolio, UpdatePortfolio, DeletePortfolio,
)
from app.modules.profiles.domain.entities import Portfolio
from app.modules.profiles.domain.repositories import PortfolioRepository, FreelancerProfileRepository


@pytest.fixture
def dependencies():
    profiles = MagicMock(spec=FreelancerProfileRepository)
    repository = MagicMock(spec=PortfolioRepository)
    uow = MagicMock(spec=UnitOfWork)
    repository.add.side_effect = lambda item: replace(
        item, created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
    )
    repository.update.side_effect = repository.add.side_effect
    return profiles, repository, uow


def execute_write(operation, dependencies, **changes):
    profiles, repository, uow = dependencies
    values = {"title": "Branding", "description": "Desain untuk UMKM", "project_url": None}
    values.update(changes)
    if operation == "create":
        return CreatePortfolio(profiles, repository, uow).execute(
            "owner-1", CreatePortfolioInput(**values),
        )
    return UpdatePortfolio(repository, uow).execute(
        "owner-1", "own-a", UpdatePortfolioInput(**values),
    )


@pytest.mark.parametrize("operation", ["create", "update"])
def test_portfolio_write_cleans_metadata_and_returns_database_timestamps(dependencies, operation):
    profiles, repository, uow = dependencies
    result = execute_write(operation, dependencies, title="  Branding  ", description="  Desain  ")
    assert result.title == "Branding"
    assert result.description == "Desain"
    assert result.freelancer_id == "owner-1"
    assert result.project_url is None
    assert result.created_at == datetime(2026, 1, 1)
    if operation == "create":
        UUID(result.id)
        profiles.get_by_user_id.assert_called_once_with("owner-1")
        saved = repository.add.call_args.args[0]
    else:
        assert result.id == "own-a"
        saved = repository.update.call_args.args[0]
    assert saved.created_at is None and saved.updated_at is None
    uow.commit.assert_called_once()


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("changes", [
    {"title": ""}, {"title": "   "}, {"title": "a" * 181},
    {"description": ""}, {"description": "   "}, {"description": "a" * 65536},
    {"description": "\U0001f600" * 16384}, {"description": "\ud800"},
    {"project_url": ""}, {"project_url": "   "},
    {"project_url": "https://example.com/" + "a" * 1000},
    {"project_url": "javascript:alert(1)"}, {"project_url": "ftp://example.com/a"},
    {"project_url": "/relative"}, {"project_url": "https://"},
    {"project_url": "https://user:password@example.com"},
    {"project_url": "https://example.com:99999"},
    {"project_url": "https://exa mple.com"}, {"project_url": "https://example.com/\npath"},
    {"project_url": "https://example.com\\@evil.com"},
    {"project_url": "https://-bad.example"}, {"project_url": "https://example.com/%zz"},
    pytest.param({"project_url": "https://[::1]garbage/work"}, id="bracket_suffix"),
    pytest.param({"project_url": "https://example.com../work"}, id="empty_dns_label"),
])
def test_portfolio_invalid_metadata_never_writes(dependencies, operation, changes):
    _, repository, uow = dependencies
    with pytest.raises(BadRequestError):
        execute_write(operation, dependencies, **changes)
    repository.add.assert_not_called()
    repository.update.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("url", [None, "https://example.com/work?q=design#preview", "http://example.com", "https://[::1]:8080/work"])
def test_portfolio_accepts_optional_http_urls_and_utf8_capacity(dependencies, operation, url):
    description = "\U0001f600" * 16383 + "abc"
    result = execute_write(operation, dependencies, title="a" * 180, description=description, project_url=url)
    assert result.description == description
    assert result.project_url == url


def test_portfolio_url_at_maximum_length(dependencies):
    url = "https://example.com/" + "a" * (1000 - len("https://example.com/"))
    assert execute_write("create", dependencies, project_url=url).project_url == url


def test_create_portfolio_requires_profile(dependencies):
    profiles, repository, uow = dependencies
    profiles.get_by_user_id.return_value = None
    with pytest.raises(NotFoundError, match="Profil Freelancer"):
        execute_write("create", dependencies)
    repository.add.assert_not_called()
    uow.commit.assert_not_called()


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_missing_or_foreign_portfolio_does_not_commit(dependencies, operation):
    _, repository, uow = dependencies
    repository.get_by_id.return_value = None
    repository.update.side_effect = None
    repository.update.return_value = None
    repository.delete.return_value = False
    with pytest.raises(NotFoundError, match="Portfolio tidak ditemukan"):
        if operation == "get":
            GetPortfolio(repository).execute("owner-1", "foreign")
        elif operation == "update":
            execute_write("update", dependencies)
        else:
            DeletePortfolio(repository, uow).execute("owner-1", "foreign")
    uow.commit.assert_not_called()


def test_get_and_delete_scope_by_authenticated_owner(dependencies):
    _, repository, uow = dependencies
    item = Portfolio("own-a", "owner-1", "Title", "Description")
    repository.get_by_id.return_value = item
    assert GetPortfolio(repository).execute("owner-1", "own-a") == item
    repository.get_by_id.assert_called_once_with("own-a", "owner-1")
    uow.commit.assert_not_called()
    repository.delete.return_value = True
    DeletePortfolio(repository, uow).execute("owner-1", "own-a")
    repository.delete.assert_called_once_with("own-a", "owner-1")
    uow.commit.assert_called_once()


@pytest.mark.parametrize("count,has_more", [(0, False), (2, False), (3, True)])
def test_list_portfolios_bounds_results_and_scopes_query(dependencies, count, has_more):
    _, repository, _ = dependencies
    items = [Portfolio(str(i), "owner-1", "Title", "Description") for i in range(count)]
    repository.list_by_freelancer_id.return_value = items
    page = GetPortfolios(repository).execute("owner-1", limit=2, offset=1)
    assert page.items == items[:2]
    assert (page.limit, page.offset, page.has_more) == (2, 1, has_more)
    repository.list_by_freelancer_id.assert_called_once_with("owner-1", 3, 1)


@pytest.mark.parametrize("limit,offset", [(0, 0), (101, 0), (20, -1), (20, 10001), (True, 0), (1.5, 0)])
def test_list_portfolios_rejects_unbounded_pagination(dependencies, limit, offset):
    _, repository, _ = dependencies
    with pytest.raises(BadRequestError):
        GetPortfolios(repository).execute("owner-1", limit, offset)
    repository.list_by_freelancer_id.assert_not_called()


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
def test_portfolio_storage_failure_does_not_commit(dependencies, operation):
    _, repository, uow = dependencies
    getattr(repository, "add" if operation == "create" else operation).side_effect = RuntimeError("storage failed")
    with pytest.raises(RuntimeError, match="storage failed"):
        if operation == "delete":
            DeletePortfolio(repository, uow).execute("owner-1", "own-a")
        else:
            execute_write(operation, dependencies)
    uow.commit.assert_not_called()
