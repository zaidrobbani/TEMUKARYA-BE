from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.modules.admin_finance.application.use_cases import (
    GetFinanceSummary,
    GetIncomeChart,
    GetTransaction,
    ListCommissions,
    ListTransactions,
    wib_day_start,
)
from app.modules.admin_finance.domain.entities import IncomePeriod
from app.modules.payments.domain.entities import PaymentOutcome
from tests.modules.workflow.fakes import FREELANCER_ID, FakeAdminFinanceRepository
from tests.modules.workflow.world import FREELANCER, UMKM, World


def second_project(w, project_id, price):
    w.store.add_project(project_id, title=f"Proyek {project_id}")
    w.store.add_application(project_id=project_id, price=price)
    w.select(project_id=project_id, application_id=f"app-{FREELANCER_ID}-{project_id}")
    w.set_plan(project_id=project_id)
    w.approve(FREELANCER, project_id=project_id)
    w.approve(UMKM, project_id=project_id)


@pytest.fixture
def w():
    world = World()
    world.to_completed()  # project-1: 1.500.000 dibayar 10 Nov, dana RELEASED
    world.clock.advance(days=1)
    second_project(world, "p2", 1_000_000)
    world.pay(project_id="p2")  # dibayar 11 Nov, dana HELD
    second_project(world, "p3", 500_000)
    world.pay(project_id="p3", outcome=PaymentOutcome.FAILED)
    second_project(world, "p4", 200_000)
    world.cancel(project_id="p4")
    return world


def repo(w):
    return FakeAdminFinanceRepository(w.store)


def test_summary(w):
    summary = GetFinanceSummary(repo(w), w.clock).execute()
    assert summary.total_income == 75_000 + 50_000
    assert summary.income_this_month == 125_000
    assert summary.total_paid_amount == 2_500_000
    assert summary.held_amount == 950_000
    assert summary.released_amount == 1_425_000
    assert (summary.successful_transactions, summary.failed_transactions, summary.cancelled_transactions) == (2, 1, 1)
    assert summary.total_transactions == 4


def test_summary_next_month_excludes_old_income(w):
    w.clock.now = datetime(2026, 12, 2, tzinfo=UTC)
    assert GetFinanceSummary(repo(w), w.clock).execute().income_this_month == 0


def test_transactions_filters(w):
    page = ListTransactions(repo(w)).execute()
    assert page.total == 4
    assert [r.payment.status for r in ListTransactions(repo(w)).execute(status="GAGAL").items] == ["GAGAL"]
    assert ListTransactions(repo(w)).execute(fund_status="HELD").items[0].project_id == "p2"
    assert ListTransactions(repo(w)).execute(search="proyek p3").total == 1
    by_day = ListTransactions(repo(w)).execute(date_from=date(2026, 11, 11), date_to=date(2026, 11, 11))
    assert [r.project_id for r in by_day.items] == ["p2"]
    paged = ListTransactions(repo(w)).execute(limit=1)
    assert len(paged.items) == 1 and paged.has_more is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "ASAL"},
        {"fund_status": "ASAL"},
        {"search": "x" * 101},
        {"date_from": date(2026, 11, 12), "date_to": date(2026, 11, 1)},
        {"limit": 0},
        {"offset": -1},
    ],
)
def test_transactions_invalid(w, kwargs):
    with pytest.raises(BadRequestError):
        ListTransactions(repo(w)).execute(**kwargs)


def test_transaction_detail(w):
    payment = w.store.payment_for("p3")
    detail = GetTransaction(repo(w)).execute(payment.id)
    assert detail.transaction.project_title == "Proyek p3"
    assert [a.status for a in detail.attempts] == ["FAILED"]
    with pytest.raises(NotFoundError):
        GetTransaction(repo(w)).execute("nope")


def test_commissions(w):
    page = ListCommissions(repo(w)).execute()
    assert page.total == 2
    assert page.total_commission == 125_000
    assert page.total_gross_amount == 2_500_000
    only_nov_10 = ListCommissions(repo(w)).execute(date(2026, 11, 10), date(2026, 11, 10))
    assert (only_nov_10.total, only_nov_10.total_commission) == (1, 75_000)


def test_income_chart_daily_zero_filled(w):
    chart = GetIncomeChart(repo(w), w.clock).execute(IncomePeriod.DAY, date(2026, 11, 9), date(2026, 11, 12))
    assert [(p.period_start.day, p.income, p.transactions) for p in chart.points] == [
        (9, 0, 0),
        (10, 75_000, 1),
        (11, 50_000, 1),
        (12, 0, 0),
    ]
    assert chart.points[1].label == "10 Nov"
    assert chart.total_income == 125_000


def test_income_chart_defaults(w):
    daily = GetIncomeChart(repo(w), w.clock).execute()
    assert len(daily.points) == 30 and daily.date_to == date(2026, 11, 11)
    monthly = GetIncomeChart(repo(w), w.clock).execute(IncomePeriod.MONTH)
    assert len(monthly.points) == 12
    assert monthly.points[-1].label == "Nov 2026"
    assert monthly.points[-1].income == 125_000
    assert monthly.date_from == date(2025, 12, 1)


def test_income_uses_wib_day(w):
    payment = w.store.payment_for("p2")
    # 23.30 WIB tanggal 11 = 16.30 UTC
    w.store.payments[payment.id] = payment.__class__(
        **{**payment.__dict__, "paid_at": datetime(2026, 11, 11, 16, 30, tzinfo=UTC)}
    )
    chart = GetIncomeChart(repo(w), w.clock).execute(IncomePeriod.DAY, date(2026, 11, 11), date(2026, 11, 12))
    assert [p.income for p in chart.points] == [50_000, 0]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"date_from": date(2026, 11, 12), "date_to": date(2026, 11, 1)},
        {"date_from": date(2024, 1, 1), "date_to": date(2026, 1, 1)},
        {"period": IncomePeriod.MONTH, "date_from": date(2020, 1, 1), "date_to": date(2026, 1, 1)},
    ],
)
def test_income_chart_invalid_range(w, kwargs):
    with pytest.raises(BadRequestError):
        GetIncomeChart(repo(w), w.clock).execute(**kwargs)


def test_wib_day_start():
    assert wib_day_start(date(2026, 11, 10)) == datetime(2026, 11, 9, 17, tzinfo=UTC)
    assert wib_day_start(date(2026, 11, 10)) + timedelta(hours=7) == datetime(2026, 11, 10, tzinfo=UTC)
