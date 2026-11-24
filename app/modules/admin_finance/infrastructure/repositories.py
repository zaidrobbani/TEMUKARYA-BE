from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import from_db_utc, to_db_utc
from app.modules.admin_finance.domain.entities import (
    AdminTransaction,
    AdminTransactionDetail,
    FinanceSummary,
    PaidRow,
    TransactionFilter,
)
from app.modules.admin_finance.domain.repositories import AdminFinanceRepository
from app.modules.payments.infrastructure.models import PaymentAttemptModel, PaymentModel
from app.modules.payments.infrastructure.repositories import to_attempt, to_payment

_FROM = """
    FROM payments p
    JOIN project_agreements a ON a.id = p.agreement_id
    JOIN projects pr ON pr.id = a.project_id
    JOIN users uu ON uu.id = pr.umkm_id
    LEFT JOIN umkm_profiles up ON up.user_id = pr.umkm_id
    JOIN users fu ON fu.id = a.freelancer_id
"""


def _like(search: str) -> str:
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _where(filters: TransactionFilter) -> tuple[str, dict]:
    clauses, params = ["1 = 1"], {}
    if filters.status:
        clauses.append("p.status = :status")
        params["status"] = filters.status
    if filters.fund_status:
        clauses.append("p.fund_status = :fund_status")
        params["fund_status"] = filters.fund_status
    if filters.search:
        clauses.append(
            "(pr.title LIKE :search OR p.transaction_number LIKE :search OR uu.name LIKE :search "
            "OR up.business_name LIKE :search OR fu.name LIKE :search)"
        )
        params["search"] = _like(filters.search)
    if filters.paid_from:
        clauses.append("p.paid_at >= :paid_from")
        params["paid_from"] = to_db_utc(filters.paid_from)
    if filters.paid_to:
        clauses.append("p.paid_at < :paid_to")
        params["paid_to"] = to_db_utc(filters.paid_to)
    return " WHERE " + " AND ".join(clauses), params


class SqlAlchemyAdminFinanceRepository(AdminFinanceRepository):
    def __init__(self, session: Session):
        self._session = session

    def summary(self, month_start: datetime, month_end: datetime) -> FinanceSummary:
        row = self._session.execute(
            text(
                """
                SELECT
                  COALESCE(SUM(CASE WHEN status = 'BERHASIL' THEN platform_fee_amount END), 0) AS total_income,
                  COALESCE(SUM(CASE WHEN status = 'BERHASIL' AND paid_at >= :ms AND paid_at < :me
                                    THEN platform_fee_amount END), 0) AS income_this_month,
                  COALESCE(SUM(CASE WHEN status = 'BERHASIL' THEN gross_amount END), 0) AS total_paid,
                  COALESCE(SUM(CASE WHEN fund_status = 'HELD' THEN freelancer_amount END), 0) AS held,
                  COALESCE(SUM(CASE WHEN fund_status = 'RELEASED' THEN freelancer_amount END), 0) AS released,
                  COALESCE(SUM(status = 'BERHASIL'), 0) AS ok_count,
                  COALESCE(SUM(status = 'MENUNGGU'), 0) AS pending_count,
                  COALESCE(SUM(status = 'GAGAL'), 0) AS failed_count,
                  COALESCE(SUM(status = 'DIBATALKAN'), 0) AS cancelled_count,
                  COUNT(*) AS total_count
                FROM payments
                """
            ),
            {"ms": to_db_utc(month_start), "me": to_db_utc(month_end)},
        ).mappings().one()
        return FinanceSummary(
            total_income=int(row["total_income"]),
            income_this_month=int(row["income_this_month"]),
            total_paid_amount=int(row["total_paid"]),
            held_amount=int(row["held"]),
            released_amount=int(row["released"]),
            successful_transactions=int(row["ok_count"]),
            pending_transactions=int(row["pending_count"]),
            failed_transactions=int(row["failed_count"]),
            cancelled_transactions=int(row["cancelled_count"]),
            total_transactions=int(row["total_count"]),
        )

    def _rows(self, where: str, params: dict, suffix: str = "") -> list[AdminTransaction]:
        rows = self._session.execute(
            text(
                "SELECT p.id AS payment_id, pr.id AS project_id, pr.title, pr.status AS project_status, "
                "uu.id AS umkm_id, uu.name AS umkm_name, up.business_name, fu.id AS freelancer_id, "
                "fu.name AS freelancer_name" + _FROM + where + suffix
            ),
            params,
        ).mappings().all()
        if not rows:
            return []
        models = {
            m.id: m
            for m in self._session.scalars(
                select(PaymentModel).where(PaymentModel.id.in_([r["payment_id"] for r in rows]))
            )
        }
        return [
            AdminTransaction(
                payment=to_payment(models[r["payment_id"]]),
                project_id=r["project_id"],
                project_title=r["title"],
                project_status=r["project_status"],
                umkm_id=r["umkm_id"],
                umkm_name=r["umkm_name"],
                umkm_business_name=r["business_name"],
                freelancer_id=r["freelancer_id"],
                freelancer_name=r["freelancer_name"],
            )
            for r in rows
        ]

    def list_transactions(self, filters: TransactionFilter, limit: int, offset: int) -> list[AdminTransaction]:
        where, params = _where(filters)
        params |= {"limit": limit, "offset": offset}
        return self._rows(
            where, params, " ORDER BY COALESCE(p.paid_at, p.created_at) DESC, p.id LIMIT :limit OFFSET :offset"
        )

    def count_transactions(self, filters: TransactionFilter) -> int:
        where, params = _where(filters)
        return int(self._session.execute(text("SELECT COUNT(*)" + _FROM + where), params).scalar_one())

    def get_transaction(self, payment_id: str) -> AdminTransactionDetail | None:
        rows = self._rows(" WHERE p.id = :pid", {"pid": payment_id})
        if not rows:
            return None
        attempts = self._session.scalars(
            select(PaymentAttemptModel)
            .where(PaymentAttemptModel.payment_id == payment_id)
            .order_by(PaymentAttemptModel.attempt_number)
        )
        return AdminTransactionDetail(rows[0], [to_attempt(m) for m in attempts])

    def paid_rows(self, start: datetime, end: datetime) -> list[PaidRow]:
        rows = self._session.execute(
            select(PaymentModel.paid_at, PaymentModel.platform_fee_amount, PaymentModel.gross_amount).where(
                PaymentModel.status == "BERHASIL",
                PaymentModel.paid_at >= to_db_utc(start),
                PaymentModel.paid_at < to_db_utc(end),
            )
        ).all()
        return [PaidRow(from_db_utc(r[0]), int(r[1]), int(r[2])) for r in rows]
