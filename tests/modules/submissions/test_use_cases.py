import pytest

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.modules.reviews.application.use_cases import ReviewInput
from app.modules.submissions.domain.entities import MAX_FILE_BYTES, RevisionItem
from tests.modules.workflow.fakes import FREELANCER_ID, UMKM_ID
from tests.modules.workflow.world import (
    FREELANCER,
    OTHER_FREELANCER,
    OTHER_UMKM,
    PDF,
    PNG,
    UMKM,
    World,
    upload,
)


@pytest.fixture
def w():
    return World()


class TestSubmitResult:
    def test_files_and_note_move_to_review(self, w):
        w.to_working()

        submission = w.submit(note=" Draf v1 ", files=[upload("Mockup Pouch.pdf"), upload("logo.png", PNG)])

        assert submission.version_number == 1
        assert submission.version_label == "v1.0"
        assert submission.submission_note == "Draf v1"
        assert [f.original_file_name for f in submission.files] == ["Mockup Pouch.pdf", "logo.png"]
        assert [f.mime_type for f in submission.files] == ["application/pdf", "image/png"]
        assert len(w.storage.files) == 2
        assert w.project.status == "MENUNGGU_REVIEW"
        notification = w.store.notifications_for(UMKM_ID)[-1]
        assert notification.notification_type == "SUBMISSION_RECEIVED"
        assert notification.title == "Andi Ramadhan mengirim hasil kerja"

    def test_url_only(self, w):
        w.to_working()
        submission = w.submit(note=None, url=" https://drive.google.com/abc ")
        assert submission.result_url == "https://drive.google.com/abc"
        assert submission.files == ()

    def test_revision_creates_new_version(self, w):
        first = w.to_review()
        w.request_revision(first.id)

        second = w.submit(url="https://drive.google.com/v2")

        assert second.version_number == 2
        assert second.version_label == "v1.1"
        assert w.project.status == "MENUNGGU_REVIEW"
        assert "hasil revisi" in w.store.notifications_for(UMKM_ID)[-1].title
        assert w.get_submission(first.id).review.decision == "REVISION_REQUESTED"

    def test_requires_file_or_url(self, w):
        w.to_working()
        with pytest.raises(BadRequestError, match="Lampirkan"):
            w.submit(note="hanya catatan")
        assert w.project.status == "SEDANG_DIKERJAKAN"

    @pytest.mark.parametrize("url", ["ftp://x.com/a", "drive.google.com/a", "https://", "https://x.com/" + "a" * 1000])
    def test_invalid_url(self, w, url):
        w.to_working()
        with pytest.raises(BadRequestError, match="URL"):
            w.submit(url=url)

    def test_note_too_long(self, w):
        w.to_working()
        with pytest.raises(BadRequestError):
            w.submit(note="x" * 5001, url="https://drive.google.com/a")

    def test_unsupported_extension(self, w):
        w.to_working()
        with pytest.raises(UnsupportedMediaTypeError):
            w.submit(files=[upload("virus.exe", b"MZ" + b"x" * 10)])

    def test_content_must_match_extension(self, w):
        w.to_working()
        with pytest.raises(BadRequestError, match="tidak sesuai"):
            w.submit(files=[upload("mockup.pdf", PNG)])

    def test_file_too_large(self, w):
        w.to_working()
        with pytest.raises(PayloadTooLargeError):
            w.submit(files=[upload("big.pdf", PDF, size=MAX_FILE_BYTES + 1)])

    def test_empty_file(self, w):
        w.to_working()
        with pytest.raises(BadRequestError, match="kosong"):
            w.submit(files=[upload("kosong.pdf", b"", size=0)])

    def test_too_many_files(self, w):
        w.to_working()
        with pytest.raises(BadRequestError, match="Maksimal"):
            w.submit(files=[upload(f"f{i}.pdf") for i in range(11)])

    def test_other_formats_accepted(self, w):
        w.to_working()
        files = [
            upload("a.ai", b"%!PS-Adobe-3.0"),
            upload("b.psd", b"8BPS" + b"\x00" * 10),
            upload("c.zip", b"PK\x03\x04" + b"\x00" * 10),
            upload("d.JPG", b"\xff\xd8\xff\xe0" + b"\x00" * 10),
            upload("e.mp4", b"\x00\x00\x00\x18ftypmp42"),
            upload("f.docx", b"PK\x03\x04" + b"\x00" * 10),
        ]
        submission = w.submit(files=files)
        assert len(submission.files) == 6

    def test_only_selected_freelancer(self, w):
        w.to_working()
        with pytest.raises(ForbiddenError):
            w.submit(UMKM, url="https://drive.google.com/a")
        with pytest.raises(NotFoundError):
            w.submit(OTHER_FREELANCER, url="https://drive.google.com/a")

    @pytest.mark.parametrize(
        "setup, message",
        [("to_ready", "Mulai Pengerjaan"), ("to_review", "sedang ditinjau"), ("to_completed", "sudah selesai")],
    )
    def test_wrong_status(self, w, setup, message):
        getattr(w, setup)()
        with pytest.raises(ConflictError, match=message):
            w.submit(url="https://drive.google.com/a")

    def test_storage_cleaned_when_save_fails_midway(self, w):
        w.to_working()
        w.uow.commit = lambda: (_ for _ in ()).throw(RuntimeError("db mati"))
        with pytest.raises(RuntimeError):
            w.submit(files=[upload("a.pdf"), upload("b.pdf")])
        assert w.storage.files == {}
        assert len(w.storage.deleted) == 2


class TestReadSubmissions:
    def test_both_parties_can_list(self, w):
        first = w.to_review()
        w.request_revision(first.id)
        w.submit(url="https://drive.google.com/v2")

        result = w.list_submissions(UMKM)

        assert [s.version_number for s in result.items] == [2, 1]
        assert result.revision_count == 1
        assert w.list_submissions(FREELANCER).items[0].version_number == 2

    def test_outsider_rejected(self, w):
        w.to_review()
        with pytest.raises(NotFoundError):
            w.list_submissions(OTHER_UMKM)

    def test_open_project_without_agreement(self, w):
        with pytest.raises(NotFoundError):
            w.list_submissions(UMKM)

    def test_download_file(self, w):
        w.to_working()
        submission = w.submit(files=[upload("mockup.pdf")])
        file, stream = w.open_file(submission.id, submission.files[0].id)
        assert file.original_file_name == "mockup.pdf"
        assert stream.read() == PDF

    def test_download_unknown_file(self, w):
        submission = w.to_review()
        with pytest.raises(NotFoundError):
            w.open_file(submission.id, "nope")
        with pytest.raises(NotFoundError):
            w.open_file("nope", "nope")

    def test_get_unknown_submission(self, w):
        w.to_review()
        with pytest.raises(NotFoundError):
            w.get_submission("nope")


class TestRequestRevision:
    def test_structured_revision(self, w):
        submission = w.to_review()

        result = w.request_revision(
            submission.id,
            note=None,
            focus_areas=("Tipografi & Teks", " Motif Batik Kawung ", "Tipografi & Teks"),
            items=(
                RevisionItem("Ketebalan Nama Varian", "Font semi-bold", "Label depan"),
                RevisionItem("Kontras Ornamen", "Naikkan kontras motif"),
            ),
        )

        review = result.review
        assert review.decision == "REVISION_REQUESTED"
        assert review.focus_areas == ("Tipografi & Teks", "Motif Batik Kawung")
        assert review.review_note == "1. Ketebalan Nama Varian: Font semi-bold\n2. Kontras Ornamen: Naikkan kontras motif"
        assert w.project.status == "REVISI"
        assert w.store.history[-1].change_reason == review.review_note
        notification = w.store.notifications_for(FREELANCER_ID)[-1]
        assert notification.notification_type == "REVISION_REQUESTED"
        assert "Revisi ke-1" in notification.body
        assert w.store.payment_for().fund_status == "HELD"

    @pytest.mark.parametrize(
        "data, message",
        [
            ({"note": None}, "wajib diisi"),
            ({"note": "   "}, "wajib diisi"),
            ({"note": "x" * 5001}, "maksimal"),
            ({"focus_areas": ("",)}, "Aspek"),
            ({"focus_areas": tuple(str(i) for i in range(11))}, "Maksimal"),
            ({"items": (RevisionItem("", "detail"),)}, "Judul"),
            ({"items": (RevisionItem("judul", " "),)}, "Uraian"),
            ({"items": (RevisionItem("judul", "detail", "a" * 121),)}, "Area"),
            ({"items": tuple(RevisionItem("j", "d") for _ in range(21))}, "Maksimal"),
        ],
    )
    def test_invalid_payload(self, w, data, message):
        submission = w.to_review()
        with pytest.raises(BadRequestError, match=message):
            w.request_revision(submission.id, **data)
        assert w.project.status == "MENUNGGU_REVIEW"

    def test_only_owner(self, w):
        submission = w.to_review()
        with pytest.raises(ForbiddenError):
            w.request_revision(submission.id, FREELANCER)
        with pytest.raises(NotFoundError):
            w.request_revision(submission.id, OTHER_UMKM)

    def test_old_version_rejected(self, w):
        first = w.to_review()
        w.request_revision(first.id)
        w.submit(url="https://drive.google.com/v2")
        with pytest.raises(ConflictError, match="terbaru"):
            w.request_revision(first.id)

    def test_twice_rejected(self, w):
        submission = w.to_review()
        w.request_revision(submission.id)
        with pytest.raises(ConflictError, match="Menunggu Review"):
            w.request_revision(submission.id)

    def test_unknown_submission(self, w):
        w.to_review()
        with pytest.raises(NotFoundError):
            w.request_revision("nope")


class TestApproveSubmission:
    def test_completes_project_and_releases_funds(self, w):
        submission = w.to_review()
        w.clock.advance(days=2)

        result = w.approve_submission(submission.id)

        assert result.project.status == "SELESAI"
        assert result.project.completed_at == w.clock.now
        assert result.submission.review.decision == "APPROVED"
        assert result.payment.fund_status == "RELEASED"
        assert result.payment.freelancer_amount == 1_425_000
        assert result.review is None
        types = [n.notification_type for n in w.store.notifications_for(FREELANCER_ID)[-2:]]
        assert types == ["SUBMISSION_APPROVED", "FUNDS_RELEASED"]
        assert "Rp1.425.000" in w.store.notifications_for(FREELANCER_ID)[-1].body

    def test_with_review_in_same_step(self, w):
        submission = w.to_review()

        result = w.approve_submission(
            submission.id, review=ReviewInput(5, "Responsif!", ("TEPAT_WAKTU", "RESPONSIF_KOMUNIKATIF"))
        )

        assert result.review.rating == 5
        assert result.review.highlights == ("TEPAT_WAKTU", "RESPONSIF_KOMUNIKATIF")
        assert w.store.reviews["project-1"].review_text == "Responsif!"

    def test_invalid_review_rejected_before_any_change(self, w):
        submission = w.to_review()
        with pytest.raises(BadRequestError, match="Rating"):
            w.approve_submission(submission.id, review=ReviewInput(6))
        assert w.project.status == "MENUNGGU_REVIEW"
        assert w.store.payment_for().fund_status == "HELD"

    def test_repeat_is_idempotent(self, w):
        submission = w.to_review()
        w.approve_submission(submission.id)
        commits, notifications, history = w.uow.commits, len(w.store.notifications), len(w.store.history)

        result = w.approve_submission(submission.id)

        assert result.already_completed is True
        assert result.payment.fund_status == "RELEASED"
        assert (w.uow.commits, len(w.store.notifications), len(w.store.history)) == (commits, notifications, history)
        assert w.wallet().available == 1_425_000

    def test_only_owner(self, w):
        submission = w.to_review()
        with pytest.raises(ForbiddenError):
            w.approve_submission(submission.id, FREELANCER)
        with pytest.raises(NotFoundError):
            w.approve_submission(submission.id, OTHER_UMKM)

    def test_during_revision_rejected(self, w):
        submission = w.to_review()
        w.request_revision(submission.id)
        with pytest.raises(ConflictError):
            w.approve_submission(submission.id)
        assert w.store.payment_for().fund_status == "HELD"

    def test_old_version_rejected(self, w):
        first = w.to_review()
        w.request_revision(first.id)
        latest = w.submit(url="https://drive.google.com/v2")
        with pytest.raises(ConflictError, match="terbaru"):
            w.approve_submission(first.id)
        assert w.approve_submission(latest.id).project.status == "SELESAI"


class TestReviews:
    def test_create_after_completion(self, w):
        w.to_completed()

        review = w.create_review(rating=4, review_text="  Bagus ", highlights=("TEPAT_WAKTU",))

        assert (review.rating, review.review_text, review.highlights) == (4, "Bagus", ("TEPAT_WAKTU",))
        assert w.store.notifications_for(FREELANCER_ID)[-1].notification_type == "REVIEW_RECEIVED"
        assert w.get_review(FREELANCER).id == review.id

    def test_not_completed(self, w):
        w.to_review()
        with pytest.raises(ConflictError, match="setelah proyek selesai"):
            w.create_review()

    def test_twice(self, w):
        w.to_completed()
        w.create_review()
        with pytest.raises(ConflictError, match="sudah diberi ulasan"):
            w.create_review()

    def test_only_owner(self, w):
        w.to_completed()
        with pytest.raises(ForbiddenError):
            w.create_review(FREELANCER)
        with pytest.raises(NotFoundError):
            w.create_review(OTHER_UMKM)

    @pytest.mark.parametrize(
        "data", [{"rating": 0}, {"rating": 6}, {"review_text": "x" * 2001}, {"highlights": ("ASAL",)}]
    )
    def test_invalid(self, w, data):
        w.to_completed()
        with pytest.raises(BadRequestError):
            w.create_review(**data)

    def test_get_missing(self, w):
        w.to_completed()
        with pytest.raises(NotFoundError, match="belum diberi ulasan"):
            w.get_review()

    def test_freelancer_public_reviews(self, w):
        w.to_completed()
        w.create_review(rating=4, review_text="Mantap")

        page = w.freelancer_reviews()

        assert (page.summary.average_rating, page.summary.review_count) == (4.0, 1)
        assert page.items[0].reviewer.business_name == "Kedai Kopi Senja"
        assert page.items[0].project_title == "Rebranding Pouch Kopi"

    def test_freelancer_without_reviews(self, w):
        page = w.freelancer_reviews()
        assert (page.summary.average_rating, page.summary.review_count, page.items) == (None, 0, [])

    def test_unknown_freelancer(self, w):
        with pytest.raises(NotFoundError):
            w.freelancer_reviews(UMKM_ID)

    @pytest.mark.parametrize("kwargs", [{"limit": 0}, {"offset": -1}])
    def test_invalid_page(self, w, kwargs):
        with pytest.raises(BadRequestError):
            w.freelancer_reviews(**kwargs)
