from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_uow
from app.core.unit_of_work import UnitOfWork
from app.modules.notifications.application.use_cases import Notifier
from app.modules.notifications.presentation.dependencies import get_notifier
from app.modules.payments.application.use_cases import (
    FundReleaser,
    GetProjectPayment,
    GetWallet,
    ListPaymentHistory,
    ListWalletEntries,
    RefreshQris,
    SimulatePayment,
)
from app.modules.payments.domain.repositories import PaymentRepository, WalletRepository
from app.modules.payments.infrastructure.repositories import SqlAlchemyPaymentRepository, SqlAlchemyWalletRepository
from app.modules.workflow.domain.repositories import WorkflowRepository
from app.modules.workflow.presentation.providers import get_workflow_repository


def get_payment_repository(db: Session = Depends(get_db)) -> PaymentRepository:
    return SqlAlchemyPaymentRepository(db)


def get_wallet_repository(db: Session = Depends(get_db)) -> WalletRepository:
    return SqlAlchemyWalletRepository(db)


def get_fund_releaser(
    payments: PaymentRepository = Depends(get_payment_repository),
    wallets: WalletRepository = Depends(get_wallet_repository),
) -> FundReleaser:
    return FundReleaser(payments, wallets)


def get_project_payment_use_case(
    workflow: WorkflowRepository = Depends(get_workflow_repository),
    payments: PaymentRepository = Depends(get_payment_repository),
) -> GetProjectPayment:
    return GetProjectPayment(workflow, payments)


def refresh_qris_use_case(
    workflow: WorkflowRepository = Depends(get_workflow_repository),
    payments: PaymentRepository = Depends(get_payment_repository),
    uow: UnitOfWork = Depends(get_uow),
) -> RefreshQris:
    return RefreshQris(workflow, payments, uow)


def simulate_payment_use_case(
    workflow: WorkflowRepository = Depends(get_workflow_repository),
    payments: PaymentRepository = Depends(get_payment_repository),
    wallets: WalletRepository = Depends(get_wallet_repository),
    notifier: Notifier = Depends(get_notifier),
    uow: UnitOfWork = Depends(get_uow),
) -> SimulatePayment:
    return SimulatePayment(workflow, payments, wallets, notifier, uow)


def list_payment_history_use_case(
    payments: PaymentRepository = Depends(get_payment_repository),
) -> ListPaymentHistory:
    return ListPaymentHistory(payments)


def get_wallet_use_case(wallets: WalletRepository = Depends(get_wallet_repository)) -> GetWallet:
    return GetWallet(wallets)


def list_wallet_entries_use_case(wallets: WalletRepository = Depends(get_wallet_repository)) -> ListWalletEntries:
    return ListWalletEntries(wallets)
