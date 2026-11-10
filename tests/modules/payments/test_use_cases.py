from datetime import timedelta

import pytest

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.modules.payments.domain.entities import (
    PaymentOutcome,
    TransactionGroup,
    WalletEntryFilter,
    generate_transaction_number,
    split_amount,
)
from tests.modules.workflow.fakes import FREELANCER_ID, NOW, PROJECT_ID, UMKM_ID
from tests.modules.workflow.world import FREELANCER, OTHER_FREELANCER, OTHER_UMKM, UMKM, World


@pytest.fixture
def w():
    return World()


class TestSplit:
    @pytest.mark.parametrize(
        "gross, fee, net",
        [(100_000, 5_000, 95_000), (500_000, 25_000, 475_000), (1_000_000, 50_000, 950_000), (1_999, 99, 1_900), (1, 0, 1)],
    )
    def test_commission_floor(self, gross, fee, net):
        assert split_amount(gross) == (fee, net)

    @pytest.mark.parametrize("gross", [0, -1, 10.5, True])
    def test_invalid_amount(self, gross):
        with pytest.raises(ValueError):
            split_amount(gross)

    def test_transaction_number_uses_wib_date(self):
        number = generate_transaction_number(NOW.replace(hour=20))
        assert number.startswith("TMK-20261111-")
        assert len(number) == len("TMK-20261111-00000")


class TestGetPayment:
    def test_detail_for_umkm_and_selected_freelancer(self, w):
        w.to_waiting_payment()

        detail = w.get_payment(UMKM)

        assert detail.payment.status == "MENUNGGU"
        assert detail.parties.freelancer.subtitle == "Desainer Grafis"
        assert detail.agreement.duration_days == 14
        assert w.get_payment(FREELANCER).payment.id == detail.payment.id

    def test_not_available_before_agreement_final(self, w):
        w.to_negotiation()
        with pytest.raises(NotFoundError, match="Tagihan pembayaran belum tersedia"):
            w.get_payment(UMKM)

    def test_outsider_gets_404(self, w):
        w.to_waiting_payment()
        with pytest.raises(NotFoundError, match="Proyek tidak ditemukan"):
            w.get_payment(OTHER_UMKM)
        with pytest.raises(NotFoundError):
            w.get_payment(OTHER_FREELANCER)


class TestSimulatePayment:
    def test_success_holds_funds_and_moves_project(self, w):
        w.to_waiting_payment()
        w.clock.advance(minutes=5)

        result = w.pay(key="pay-key-0001")

        payment = result.detail.payment
        assert payment.status == "BERHASIL"
        assert payment.fund_status == "HELD"
        assert payment.paid_at == w.clock.now
        assert payment.transaction_number == "TMK-20261110-00000"
        assert result.attempt.status == "SUCCEEDED"
        assert result.attempt.attempt_number == 1
        assert w.project.status == "SIAP_DIKERJAKAN"
        assert w.store.history[-1].change_source == "SYSTEM"
        assert w.store.history[-1].action == "PAYMENT_SUCCEEDED"
        balance = w.wallet()
        assert (balance.held, balance.available, balance.total) == (1_425_000, 0, 1_425_000)
        assert w.store.notifications_for(UMKM_ID)[-1].notification_type == "PAYMENT_SUCCEEDED"
        assert "Rp1.500.000" in w.store.notifications_for(UMKM_ID)[-1].body
        assert w.store.notifications_for(FREELANCER_ID)[-1].notification_type == "PAYMENT_RECEIVED"

    def test_double_pay_returns_previous_without_new_records(self, w):
        w.to_ready()
        attempts, txs = len(w.store.attempts), len(w.store.wallet_txs)

        result = w.pay()

        assert result.already_paid is True
        assert result.attempt is None
        assert len(w.store.attempts) == attempts
        assert len(w.store.wallet_txs) == txs
        assert w.wallet().held == 1_425_000

    def test_idempotency_key_replay(self, w):
        w.to_waiting_payment()
        first = w.pay(key="same-key-123")

        second = w.pay(key="same-key-123")

        assert second.replayed is True
        assert second.attempt.id == first.attempt.id
        assert len(w.store.attempts) == 1

    def test_idempotency_key_of_other_payment_rejected(self, w):
        w.to_waiting_payment()
        w.pay(key="shared-key-99")
        w.store.add_project("project-2")
        w.store.add_application(project_id="project-2")
        w.select(project_id="project-2", application_id=f"app-{FREELANCER_ID}-project-2")
        w.set_plan(project_id="project-2")
        w.approve(FREELANCER, project_id="project-2")
        w.approve(UMKM, project_id="project-2")
        with pytest.raises(ConflictError, match="Idempotency-Key"):
            w.pay(key="shared-key-99", project_id="project-2")

    @pytest.mark.parametrize("key", ["short", "x" * 65, "ada spasi 123", "kunci/garis"])
    def test_invalid_idempotency_key(self, w, key):
        w.to_waiting_payment()
        with pytest.raises(BadRequestError, match="Idempotency-Key"):
            w.pay(key=key)

    def test_failed_simulation_then_refresh_and_retry(self, w):
        w.to_waiting_payment()

        failed = w.pay(outcome=PaymentOutcome.FAILED)

        assert failed.detail.payment.status == "GAGAL"
        assert failed.attempt.failure_reason == "Simulasi pembayaran gagal"
        assert w.project.status == "MENUNGGU_PEMBAYARAN"
        assert w.store.wallets == {}
        assert w.store.notifications_for(UMKM_ID)[-1].notification_type == "PAYMENT_FAILED"

        with pytest.raises(ConflictError) as error:
            w.pay()
        assert error.value.code == "QRIS_REFRESH_REQUIRED"

        w.clock.advance(minutes=1)
        refreshed = w.refresh_qris()
        assert refreshed.payment.status == "MENUNGGU"
        assert refreshed.payment.expires_at == w.clock.now + timedelta(minutes=15)

        success = w.pay()
        assert success.attempt.attempt_number == 2
        assert success.detail.payment.status == "BERHASIL"

    def test_expired_qris_rejected(self, w):
        w.to_waiting_payment()
        w.clock.advance(minutes=15)
        with pytest.raises(ConflictError) as error:
            w.pay()
        assert error.value.code == "QRIS_EXPIRED"
        w.refresh_qris()
        assert w.pay().detail.payment.status == "BERHASIL"

    def test_only_owner_umkm_can_pay(self, w):
        w.to_waiting_payment()
        with pytest.raises(ForbiddenError):
            w.pay(FREELANCER)
        with pytest.raises(NotFoundError):
            w.pay(OTHER_UMKM)

    def test_cancelled_project_cannot_be_paid(self, w):
        w.to_waiting_payment()
        w.cancel(UMKM)
        with pytest.raises(ConflictError, match="dibatalkan"):
            w.pay()
        with pytest.raises(ConflictError, match="dibatalkan"):
            w.refresh_qris()

    def test_before_invoice(self, w):
        w.to_negotiation()
        with pytest.raises(NotFoundError):
            w.pay()

    def test_invalid_outcome(self, w):
        w.to_waiting_payment()
        with pytest.raises(BadRequestError):
            w.pay(outcome="MAYBE")

    def test_transaction_number_collision_retries(self, w):
        w.to_waiting_payment()
        w.store.payments["other"] = w.store.payment_for().__class__(
            **{**w.store.payment_for().__dict__, "id": "other", "agreement_id": "x", "transaction_number": "TMK-A"}
        )
        numbers = iter(["TMK-A", "TMK-B"])
        result = w.pay(numbers=lambda now: next(numbers))
        assert result.detail.payment.transaction_number == "TMK-B"

    def test_transaction_number_gives_up(self, w):
        w.to_waiting_payment()
        w.store.payments["other"] = w.store.payment_for().__class__(
            **{**w.store.payment_for().__dict__, "id": "other", "agreement_id": "x", "transaction_number": "TMK-A"}
        )
        with pytest.raises(ConflictError, match="nomor transaksi"):
            w.pay(numbers=lambda now: "TMK-A")
        assert w.project.status == "MENUNGGU_PEMBAYARAN"


class TestRefreshQris:
    def test_freelancer_cannot_refresh(self, w):
        w.to_waiting_payment()
        with pytest.raises(ForbiddenError):
            w.refresh_qris(FREELANCER)

    def test_paid_cannot_refresh(self, w):
        w.to_ready()
        with pytest.raises(ConflictError) as error:
            w.refresh_qris()
        assert error.value.code == "PAYMENT_ALREADY_PAID"


class TestFundRelease:
    def test_approval_releases_once(self, w):
        submission = w.to_review()

        w.approve_submission(submission.id)
        w.approve_submission(submission.id)

        balance = w.wallet()
        assert (balance.held, balance.available) == (0, 1_425_000)
        released = [t for t in w.store.wallet_txs if t.transaction_type == "FUND_RELEASED"]
        assert sorted(t.amount_delta for t in released) == [-1_425_000, 1_425_000]
        payment = w.store.payment_for()
        assert payment.fund_status == "RELEASED"
        assert payment.released_at == w.clock.now

    def test_revision_and_submission_do_not_release(self, w):
        submission = w.to_review()
        w.request_revision(submission.id)
        w.submit(url="https://drive.google.com/v2")
        assert w.store.payment_for().fund_status == "HELD"
        assert w.wallet().available == 0


class TestPaymentHistory:
    def make_paid_and_pending(self, w):
        w.to_ready()
        w.store.add_project("project-2", title="Foto Katalog Menu")
        w.store.add_application(project_id="project-2")
        w.select(project_id="project-2", application_id=f"app-{FREELANCER_ID}-project-2")
        w.set_plan(project_id="project-2")
        w.approve(FREELANCER, project_id="project-2")
        w.approve(UMKM, project_id="project-2")

    def test_groups_and_counts(self, w):
        self.make_paid_and_pending(w)

        page = w.history()

        assert len(page.items) == 2
        assert page.counts == {"ALL": 2, "PENDING": 1, "HELD": 1, "COMPLETED": 0, "CANCELLED": 0}
        held = w.history(group=TransactionGroup.HELD)
        assert [i.project_id for i in held.items] == [PROJECT_ID]
        assert held.items[0].freelancer_name == "Andi Ramadhan"
        assert held.items[0].payment.display_status == "DANA_DITAHAN"

    def test_search(self, w):
        self.make_paid_and_pending(w)
        assert [i.project_title for i in w.history(search="katalog").items] == ["Foto Katalog Menu"]
        assert w.history(search="TMK-20261110").counts["ALL"] == 1

    def test_completed_and_cancelled(self, w):
        w.to_completed()
        assert w.history(group=TransactionGroup.COMPLETED).items[0].payment.display_status == "SELESAI"

    def test_only_umkm(self, w):
        with pytest.raises(ForbiddenError):
            w.history(FREELANCER)

    @pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"search": "x" * 101}])
    def test_invalid_query(self, w, kwargs):
        with pytest.raises(BadRequestError):
            w.history(**kwargs)


class TestWallet:
    def test_empty_wallet_before_first_payment(self, w):
        balance = w.wallet()
        assert (balance.held, balance.available, balance.total) == (0, 0, 0)
        page = w.wallet_entries()
        assert page.items == [] and page.has_more is False
        assert w.store.wallets == {}

    def test_only_freelancer(self, w):
        with pytest.raises(ForbiddenError):
            w.wallet(UMKM)
        with pytest.raises(ForbiddenError):
            w.wallet_entries(UMKM)

    def test_entries_held_then_income(self, w):
        w.to_ready()
        held = w.wallet_entries()
        assert [(e.entry_type, e.amount, e.still_held) for e in held.items] == [("FUND_HELD", 1_425_000, True)]

        w.start()
        submission = w.submit(url="https://drive.google.com/x")
        w.clock.advance(days=1)
        w.approve_submission(submission.id)

        entries = w.wallet_entries()
        assert [(e.entry_type, e.amount) for e in entries.items] == [
            ("FUND_RELEASED", 1_425_000),
            ("FUND_HELD", 1_425_000),
        ]
        assert all(e.still_held is False for e in entries.items)
        assert [e.entry_type for e in w.wallet_entries(entry_filter=WalletEntryFilter.INCOME).items] == [
            "FUND_RELEASED"
        ]
        assert w.wallet_entries(entry_filter=WalletEntryFilter.HELD).items == []

    @pytest.mark.parametrize("kwargs", [{"limit": 0}, {"offset": -5}])
    def test_invalid_page(self, w, kwargs):
        with pytest.raises(BadRequestError):
            w.wallet_entries(**kwargs)
