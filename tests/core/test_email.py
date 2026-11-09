import logging
from email.utils import parsedate_to_datetime

from fastapi import BackgroundTasks

from app.core.dependencies import BackgroundEmailSender
from app.core.email import EmailMessage, SmtpEmailSender
from tests.fakes import FakeEmailSender

MESSAGE = EmailMessage(to="rina@mail.com", subject="Subjek", text="Isi")


class StubSmtp:
    instances: list["StubSmtp"] = []

    def __init__(self, host, port, timeout):
        self.host, self.port, self.timeout = host, port, timeout
        self.tls = False
        self.credentials = None
        self.sent = None
        StubSmtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def starttls(self, context):
        self.tls = True

    def login(self, username, password):
        self.credentials = (username, password)

    def send_message(self, mime):
        self.sent = mime


def run(tasks: BackgroundTasks) -> None:
    for task in tasks.tasks:
        task.func(*task.args, **task.kwargs)


def test_background_sender_sends_only_when_task_runs():
    tasks, inner = BackgroundTasks(), FakeEmailSender()

    BackgroundEmailSender(tasks, inner).send(MESSAGE)
    assert inner.sent == []

    run(tasks)
    assert inner.sent == [MESSAGE]


def test_background_sender_logs_failure_without_raising(caplog):
    class BrokenSender(FakeEmailSender):
        def send(self, message):
            raise OSError("SMTP mati")

    tasks = BackgroundTasks()
    BackgroundEmailSender(tasks, BrokenSender()).send(MESSAGE)

    with caplog.at_level(logging.ERROR):
        run(tasks)

    assert "Gagal mengirim email: Subjek" in caplog.text


def test_smtp_sender_builds_plain_text_message(monkeypatch):
    monkeypatch.setattr("app.core.email.smtplib.SMTP", StubSmtp)

    SmtpEmailSender("mailpit", 1025, "TEMUKARYA <no-reply@temukarya.id>").send(MESSAGE)

    smtp = StubSmtp.instances[-1]
    assert (smtp.host, smtp.port) == ("mailpit", 1025)
    assert smtp.tls is False and smtp.credentials is None
    assert smtp.sent["To"] == "rina@mail.com"
    assert smtp.sent["From"] == "TEMUKARYA <no-reply@temukarya.id>"
    assert parsedate_to_datetime(smtp.sent["Date"]).tzinfo is not None
    assert smtp.sent["Message-ID"].endswith("@temukarya.id>")
    assert smtp.sent.get_content_type() == "text/plain"
    assert smtp.sent.get_content().strip() == "Isi"


def test_smtp_sender_uses_tls_and_login_when_configured(monkeypatch):
    monkeypatch.setattr("app.core.email.smtplib.SMTP", StubSmtp)

    SmtpEmailSender(
        "smtp.example.com", 587, "a@b.co", username="user", password="sandi", use_tls=True
    ).send(MESSAGE)

    smtp = StubSmtp.instances[-1]
    assert smtp.tls is True
    assert smtp.credentials == ("user", "sandi")
