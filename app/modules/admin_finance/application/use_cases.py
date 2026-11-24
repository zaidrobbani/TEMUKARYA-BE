from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from app.core.exceptions import BadRequestError, NotFoundError
from app.modules.admin_finance.domain.entities import (
    AdminTransaction,
    AdminTransactionDetail,
    FinanceSummary,
    IncomePeriod,
    IncomePoint,
    TransactionFilter,
)
from app.modules.admin_finance.domain.repositories import AdminFinanceRepository
from app.modules.payments.domain.entities import FundStatus, PaymentStatus
from app.modules.workflow.application.services import Clock, utc_now
from app.modules.workflow.domain.entities import WIB, wib_date

MAX_PAGE_LIMIT = 100
MAX_SEARCH_LENGTH = 100
MAX_DAY_POINTS = 366
MAX_MONTH_POINTS = 60
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def wib_day_start(day: date) -> datetime:
    """Awal hari WIB dalam UTC."""
    return datetime.combine(day, time(), tzinfo=UTC) - WIB


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _validate_page(limit: int, offset: int) -> None:
    if not 1 <= limit <= MAX_PAGE_LIMIT:
        raise BadRequestError(f"Limit harus 1 sampai {MAX_PAGE_LIMIT}")
    if offset < 0:
        raise BadRequestError("Offset tidak boleh negatif")


def _range(date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
    if date_from and date_to and date_from > date_to:
        raise BadRequestError("date_from tidak boleh setelah date_to")
    start = wib_day_start(date_from) if date_from else None
    end = wib_day_start(date_to + timedelta(days=1)) if date_to else None
    return start, end


@dataclass(frozen=True)
class TransactionPage:
    items: list[AdminTransaction]
    total: int
    has_more: bool


@dataclass(frozen=True)
class CommissionPage:
    items: list[AdminTransaction]
    total: int
    has_more: bool
    total_commission: int
    total_gross_amount: int


@dataclass(frozen=True)
class IncomeChart:
    period: IncomePeriod
    date_from: date
    date_to: date
    points: list[IncomePoint]
    total_income: int


class GetFinanceSummary:
    """A-09 Dashboard Income."""

    def __init__(self, repository: AdminFinanceRepository, clock: Clock = utc_now):
        self._repository = repository
        self._clock = clock

    def execute(self) -> FinanceSummary:
        today = wib_date(self._clock())
        month_start = today.replace(day=1)
        return self._repository.summary(wib_day_start(month_start), wib_day_start(_add_months(month_start, 1)))


class ListTransactions:
    """A-06 Data Transaksi."""

    def __init__(self, repository: AdminFinanceRepository):
        self._repository = repository

    def execute(
        self,
        status: str | None = None,
        fund_status: str | None = None,
        search: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> TransactionPage:
        _validate_page(limit, offset)
        if status is not None and status not in {s.value for s in PaymentStatus}:
            raise BadRequestError("Status pembayaran tidak valid")
        if fund_status is not None and fund_status not in {s.value for s in FundStatus}:
            raise BadRequestError("Status dana tidak valid")
        search = (search or "").strip() or None
        if search is not None and len(search) > MAX_SEARCH_LENGTH:
            raise BadRequestError(f"Kata kunci maksimal {MAX_SEARCH_LENGTH} karakter")
        start, end = _range(date_from, date_to)
        filters = TransactionFilter(status, fund_status, search, start, end)
        rows = self._repository.list_transactions(filters, limit + 1, offset)
        return TransactionPage(rows[:limit], self._repository.count_transactions(filters), len(rows) > limit)


class GetTransaction:
    def __init__(self, repository: AdminFinanceRepository):
        self._repository = repository

    def execute(self, payment_id: str) -> AdminTransactionDetail:
        detail = self._repository.get_transaction(payment_id)
        if detail is None:
            raise NotFoundError("Transaksi tidak ditemukan")
        return detail


class ListCommissions:
    """A-07 Komisi 5% dari project yang berhasil dibayar."""

    def __init__(self, repository: AdminFinanceRepository):
        self._repository = repository

    def execute(
        self, date_from: date | None = None, date_to: date | None = None, limit: int = 20, offset: int = 0
    ) -> CommissionPage:
        _validate_page(limit, offset)
        start, end = _range(date_from, date_to)
        filters = TransactionFilter(status=PaymentStatus.BERHASIL.value, paid_from=start, paid_to=end)
        rows = self._repository.list_transactions(filters, limit + 1, offset)
        paid = self._repository.paid_rows(
            start or datetime(1970, 1, 1, tzinfo=UTC), end or datetime(9999, 1, 1, tzinfo=UTC)
        )
        return CommissionPage(
            items=rows[:limit],
            total=self._repository.count_transactions(filters),
            has_more=len(rows) > limit,
            total_commission=sum(r.platform_fee_amount for r in paid),
            total_gross_amount=sum(r.gross_amount for r in paid),
        )


class GetIncomeChart:
    """A-10 Grafik income per hari/bulan (WIB), periode tanpa transaksi bernilai 0."""

    def __init__(self, repository: AdminFinanceRepository, clock: Clock = utc_now):
        self._repository = repository
        self._clock = clock

    def execute(
        self, period: IncomePeriod = IncomePeriod.DAY, date_from: date | None = None, date_to: date | None = None
    ) -> IncomeChart:
        period = IncomePeriod(period)
        today = wib_date(self._clock())
        date_to = date_to or today
        if period == IncomePeriod.DAY:
            date_from = date_from or date_to - timedelta(days=29)
        else:
            date_from = (date_from or _add_months(date_to.replace(day=1), -11)).replace(day=1)
        if date_from > date_to:
            raise BadRequestError("date_from tidak boleh setelah date_to")

        if period == IncomePeriod.DAY:
            starts = [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]
            if len(starts) > MAX_DAY_POINTS:
                raise BadRequestError(f"Rentang harian maksimal {MAX_DAY_POINTS} hari")
            end = date_to + timedelta(days=1)
        else:
            starts = []
            cursor = date_from
            while cursor <= date_to:
                starts.append(cursor)
                cursor = _add_months(cursor, 1)
            if len(starts) > MAX_MONTH_POINTS:
                raise BadRequestError(f"Rentang bulanan maksimal {MAX_MONTH_POINTS} bulan")
            end = _add_months(date_to.replace(day=1), 1)

        buckets = {s: [0, 0, 0] for s in starts}
        for row in self._repository.paid_rows(wib_day_start(date_from), wib_day_start(end)):
            day = wib_date(row.paid_at)
            key = day if period == IncomePeriod.DAY else day.replace(day=1)
            if key in buckets:
                buckets[key][0] += row.platform_fee_amount
                buckets[key][1] += row.gross_amount
                buckets[key][2] += 1

        points = [
            IncomePoint(
                period_start=s,
                label=f"{s.day} {_MONTHS[s.month - 1]}" if period == IncomePeriod.DAY else f"{_MONTHS[s.month - 1]} {s.year}",
                income=values[0],
                gross_amount=values[1],
                transactions=values[2],
            )
            for s, values in buckets.items()
        ]
        return IncomeChart(period, date_from, date_to, points, sum(p.income for p in points))
