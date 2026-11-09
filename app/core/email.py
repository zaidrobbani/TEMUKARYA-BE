import smtplib
import ssl
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import formatdate, make_msgid, parseaddr


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str


class EmailSender(ABC):
    @abstractmethod
    def send(self, message: EmailMessage) -> None: ...


class SmtpEmailSender(EmailSender):
    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        username: str = "",
        password: str = "",
        use_tls: bool = False,
        timeout_seconds: int = 10,
    ):
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._timeout_seconds = timeout_seconds

    def send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self._sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime["Date"] = formatdate(usegmt=True)
        mime["Message-ID"] = make_msgid(domain=parseaddr(self._sender)[1].rpartition("@")[2])
        mime.set_content(message.text)

        with smtplib.SMTP(self._host, self._port, timeout=self._timeout_seconds) as smtp:
            if self._use_tls:
                smtp.starttls(context=ssl.create_default_context())
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(mime)
