import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.modules.notifications.application.use_cases import (
    CountUnreadNotifications,
    ListNotifications,
    MarkAllNotificationsRead,
    MarkNotificationRead,
    Notifier,
)
from app.modules.notifications.domain.entities import NotificationCategory, NotificationType, category_of
from tests.fakes import FakeUnitOfWork
from tests.modules.workflow.fakes import Clock, FakeNotificationRepository, Store


@pytest.fixture
def ctx():
    store, clock = Store(), Clock()
    repo = FakeNotificationRepository(store)
    notifier = Notifier(repo, clock)
    return store, clock, repo, notifier, FakeUnitOfWork()


def seed(ctx):
    store, clock, repo, notifier, _ = ctx
    notifier.notify("u1", NotificationType.APPLICATION_RECEIVED, "3 freelancer mengajukan diri", "Menunggu", "PROJECT", "p1")
    clock.advance(minutes=1)
    notifier.notify("u1", NotificationType.PAYMENT_SUCCEEDED, "Pembayaran berhasil", "Rp1.500.000 ditahan")
    clock.advance(minutes=1)
    notifier.notify("u1", NotificationType.NEW_MESSAGE, "Pesan baru", "Halo", "CONVERSATION", "c1")
    notifier.notify("u2", NotificationType.NEW_MESSAGE, "Pesan baru", "Untuk orang lain")


def test_notify_clips_and_normalizes(ctx):
    store, _, _, notifier, _ = ctx
    n = notifier.notify("u1", NotificationType.NEW_MESSAGE, "x" * 300, "baris\n  baru " + "y" * 2000)
    assert len(n.title) == 180 and n.title.endswith("…")
    assert n.body.startswith("baris baru y")
    assert len(n.body) == 1000
    assert store.notifications == [n]


def test_category_mapping():
    assert category_of("PAYMENT_SUCCEEDED") == NotificationCategory.PAYMENT
    assert category_of("FUNDS_RELEASED") == NotificationCategory.PAYMENT
    assert category_of("NEW_MESSAGE") == NotificationCategory.MESSAGE
    assert category_of("SUBMISSION_RECEIVED") == NotificationCategory.PROJECT


def test_list_newest_first_with_counts(ctx):
    seed(ctx)
    page = ListNotifications(ctx[2]).execute("u1")
    assert [n.notification_type for n in page.items] == ["NEW_MESSAGE", "PAYMENT_SUCCEEDED", "APPLICATION_RECEIVED"]
    assert page.unread_count == 3
    assert page.category_counts == {"ALL": 3, "PROJECT": 1, "PAYMENT": 1, "MESSAGE": 1}
    assert page.has_more is False


def test_filter_category_unread_and_paging(ctx):
    seed(ctx)
    repo = ctx[2]
    assert [n.notification_type for n in ListNotifications(repo).execute("u1", NotificationCategory.PAYMENT).items] == [
        "PAYMENT_SUCCEEDED"
    ]
    page = ListNotifications(repo).execute("u1", limit=2)
    assert len(page.items) == 2 and page.has_more is True
    first = page.items[0]
    MarkNotificationRead(repo, ctx[4], ctx[1]).execute("u1", first.id)
    unread = ListNotifications(repo).execute("u1", unread_only=True)
    assert first.id not in [n.id for n in unread.items]


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_invalid_page(ctx, kwargs):
    with pytest.raises(BadRequestError):
        ListNotifications(ctx[2]).execute("u1", **kwargs)


def test_mark_read_and_idempotent(ctx):
    seed(ctx)
    store, clock, repo, _, uow = ctx
    target = store.notifications[0]
    read = MarkNotificationRead(repo, uow, clock).execute("u1", target.id)
    assert read.read_at == clock.now
    clock.advance(hours=1)
    again = MarkNotificationRead(repo, uow, clock).execute("u1", target.id)
    assert again.read_at == read.read_at
    assert CountUnreadNotifications(repo).execute("u1") == 2


def test_mark_read_other_users_notification(ctx):
    seed(ctx)
    store, clock, repo, _, uow = ctx
    other = next(n for n in store.notifications if n.user_id == "u2")
    with pytest.raises(NotFoundError):
        MarkNotificationRead(repo, uow, clock).execute("u1", other.id)
    assert uow.commits == 0


def test_mark_all_read(ctx):
    seed(ctx)
    store, clock, repo, _, uow = ctx
    assert MarkAllNotificationsRead(repo, uow, clock).execute("u1") == 3
    assert MarkAllNotificationsRead(repo, uow, clock).execute("u1") == 0
    assert CountUnreadNotifications(repo).execute("u1") == 0
    assert CountUnreadNotifications(repo).execute("u2") == 1
