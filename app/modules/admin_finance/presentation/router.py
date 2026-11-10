from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.responses import ApiResponse, error_responses, success_response
from app.modules.admin_finance.application.use_cases import (
    GetFinanceSummary,
    GetIncomeChart,
    GetTransaction,
    ListCommissions,
    ListTransactions,
)
from app.modules.admin_finance.domain.entities import IncomePeriod
from app.modules.admin_finance.domain.repositories import AdminFinanceRepository
from app.modules.admin_finance.infrastructure.repositories import SqlAlchemyAdminFinanceRepository
from app.modules.admin_finance.presentation.schemas import (
    AdminTransactionDetailResponse,
    CommissionListResponse,
    FinanceSummaryResponse,
    IncomeChartResponse,
    TransactionListResponse,
)
from app.modules.auth.presentation.dependencies import require_roles
from app.modules.payments.domain.entities import FundStatus, PaymentStatus
from app.modules.users.domain.entities import UserRole

router = APIRouter(
    prefix="/admin/finance",
    tags=["admin-finance"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


def get_admin_finance_repository(db: Session = Depends(get_db)) -> AdminFinanceRepository:
    return SqlAlchemyAdminFinanceRepository(db)


@router.get(
    "/summary",
    response_model=ApiResponse[FinanceSummaryResponse],
    responses=error_responses(401, 403),
    summary="Dashboard income (komisi) TEMUKARYA",
)
def finance_summary(repository: AdminFinanceRepository = Depends(get_admin_finance_repository)):
    return success_response("Ringkasan keuangan", FinanceSummaryResponse.build(GetFinanceSummary(repository).execute()))


@router.get(
    "/transactions",
    response_model=ApiResponse[TransactionListResponse],
    responses=error_responses(400, 401, 403, 422),
    summary="Data transaksi pembayaran project",
)
def list_transactions(
    status: PaymentStatus | None = Query(None),
    fund_status: FundStatus | None = Query(None),
    search: str | None = Query(None, max_length=100, description="Judul project, nomor transaksi, nama UMKM/freelancer"),
    date_from: date | None = Query(None, description="Tanggal bayar (WIB) mulai"),
    date_to: date | None = Query(None, description="Tanggal bayar (WIB) sampai"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repository: AdminFinanceRepository = Depends(get_admin_finance_repository),
):
    page = ListTransactions(repository).execute(
        status.value if status else None,
        fund_status.value if fund_status else None,
        search,
        date_from,
        date_to,
        limit,
        offset,
    )
    return success_response("Daftar transaksi", TransactionListResponse.build(page, limit, offset))


@router.get(
    "/transactions/{payment_id}",
    response_model=ApiResponse[AdminTransactionDetailResponse],
    responses=error_responses(401, 403, 404),
)
def get_transaction(payment_id: str, repository: AdminFinanceRepository = Depends(get_admin_finance_repository)):
    detail = GetTransaction(repository).execute(payment_id)
    return success_response("Detail transaksi", AdminTransactionDetailResponse.from_detail(detail))


@router.get(
    "/commissions",
    response_model=ApiResponse[CommissionListResponse],
    responses=error_responses(400, 401, 403, 422),
    summary="Komisi 5% dari project yang berhasil dibayar",
)
def list_commissions(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repository: AdminFinanceRepository = Depends(get_admin_finance_repository),
):
    page = ListCommissions(repository).execute(date_from, date_to, limit, offset)
    return success_response("Daftar komisi", CommissionListResponse.from_page(page, limit, offset))


@router.get(
    "/income-chart",
    response_model=ApiResponse[IncomeChartResponse],
    responses=error_responses(400, 401, 403, 422),
    summary="Grafik income per hari (default 30 hari) atau per bulan (default 12 bulan)",
)
def income_chart(
    period: IncomePeriod = Query(IncomePeriod.DAY),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    repository: AdminFinanceRepository = Depends(get_admin_finance_repository),
):
    chart = GetIncomeChart(repository).execute(period, date_from, date_to)
    return success_response("Grafik income", IncomeChartResponse.build(chart))
