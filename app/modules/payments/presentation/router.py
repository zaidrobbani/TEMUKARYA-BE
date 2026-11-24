from fastapi import APIRouter, Body, Depends, Header, Query

from app.core.responses import ApiResponse, error_responses, success_response
from app.modules.payments.application.use_cases import (
    GetProjectPayment,
    GetWallet,
    ListPaymentHistory,
    ListWalletEntries,
    RefreshQris,
    SimulatePayment,
)
from app.modules.payments.domain.entities import PaymentOutcome, PaymentStatus, TransactionGroup, WalletEntryFilter
from app.modules.payments.presentation.dependencies import (
    get_project_payment_use_case,
    get_wallet_use_case,
    list_payment_history_use_case,
    list_wallet_entries_use_case,
    refresh_qris_use_case,
    simulate_payment_use_case,
)
from app.modules.payments.presentation.schemas import (
    PaymentDetailResponse,
    PaymentHistoryResponse,
    SimulatePaymentRequest,
    WalletEntriesResponse,
    WalletResponse,
)
from app.modules.workflow.application.dto import Actor
from app.modules.workflow.presentation.providers import get_actor

router = APIRouter(tags=["payments"])


@router.get(
    "/projects/{project_id}/payment",
    response_model=ApiResponse[PaymentDetailResponse],
    responses=error_responses(401, 404),
    summary="Detail pembayaran, status, dan bukti pembayaran",
)
def get_project_payment(
    project_id: str,
    actor: Actor = Depends(get_actor),
    use_case: GetProjectPayment = Depends(get_project_payment_use_case),
):
    return success_response("Detail pembayaran", PaymentDetailResponse.build(use_case.execute(actor, project_id)))


@router.post(
    "/projects/{project_id}/payment/qris",
    response_model=ApiResponse[PaymentDetailResponse],
    responses=error_responses(401, 403, 404, 409),
    summary="Buat ulang QRIS simulasi (setelah gagal atau kedaluwarsa)",
)
def refresh_qris(
    project_id: str,
    actor: Actor = Depends(get_actor),
    use_case: RefreshQris = Depends(refresh_qris_use_case),
):
    return success_response("QRIS siap dibayar", PaymentDetailResponse.build(use_case.execute(actor, project_id)))


@router.post(
    "/projects/{project_id}/payment/simulate",
    response_model=ApiResponse[PaymentDetailResponse],
    responses=error_responses(400, 401, 403, 404, 409, 422),
    summary="Bayar (simulasi). Kirim header Idempotency-Key agar klik ganda aman",
)
def simulate_payment(
    project_id: str,
    body: SimulatePaymentRequest | None = Body(None),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    actor: Actor = Depends(get_actor),
    use_case: SimulatePayment = Depends(simulate_payment_use_case),
):
    outcome = body.outcome if body else PaymentOutcome.SUCCESS
    result = use_case.execute(actor, project_id, outcome, idempotency_key)
    if result.already_paid:
        message = "Pembayaran sudah berhasil sebelumnya"
    elif result.detail.payment.status == PaymentStatus.BERHASIL:
        message = "Pembayaran berhasil, dana ditahan TEMUKARYA"
    else:
        message = "Pembayaran gagal, silakan coba lagi"
    return success_response(message, PaymentDetailResponse.build(result.detail))


@router.get(
    "/payments/history",
    response_model=ApiResponse[PaymentHistoryResponse],
    responses=error_responses(400, 401, 403, 422),
    summary="Riwayat transaksi UMKM",
)
def payment_history(
    group: TransactionGroup = Query(TransactionGroup.ALL, description="ALL, PENDING, HELD, COMPLETED, CANCELLED"),
    search: str | None = Query(None, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: Actor = Depends(get_actor),
    use_case: ListPaymentHistory = Depends(list_payment_history_use_case),
):
    page = use_case.execute(actor, group, search, limit, offset)
    return success_response("Riwayat transaksi", PaymentHistoryResponse.build(page, limit, offset))


@router.get(
    "/wallet",
    response_model=ApiResponse[WalletResponse],
    responses=error_responses(401, 403),
    summary="Saldo dompet freelancer",
)
def get_wallet(actor: Actor = Depends(get_actor), use_case: GetWallet = Depends(get_wallet_use_case)):
    return success_response("Saldo dompet", WalletResponse.build(use_case.execute(actor)))


@router.get(
    "/wallet/transactions",
    response_model=ApiResponse[WalletEntriesResponse],
    responses=error_responses(400, 401, 403, 422),
    summary="Riwayat dana masuk freelancer",
)
def wallet_transactions(
    type_filter: WalletEntryFilter = Query(WalletEntryFilter.ALL, alias="type", description="ALL, HELD, INCOME"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: Actor = Depends(get_actor),
    use_case: ListWalletEntries = Depends(list_wallet_entries_use_case),
):
    page = use_case.execute(actor, type_filter, limit, offset)
    return success_response("Riwayat dompet", WalletEntriesResponse.build(page, limit, offset))
