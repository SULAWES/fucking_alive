import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.core.config import settings


@dataclass(frozen=True)
class EmailMessagePayload:
    recipient: str
    subject: str
    body: str


class MailSender(Protocol):
    def send(self, payload: EmailMessagePayload) -> None:
        ...


class SmtpMailSender:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        from_address: str | None = None,
        use_tls: bool | None = None,
        use_ssl: bool | None = None,
    ) -> None:
        self._host = (host or settings.smtp_host).strip()
        self._port = port or settings.smtp_port
        self._username = username if username is not None else settings.smtp_username
        self._password = password if password is not None else settings.smtp_password
        self._from_address = (from_address or settings.smtp_from).strip()
        self._use_tls = settings.smtp_use_tls if use_tls is None else use_tls
        self._use_ssl = settings.smtp_use_ssl if use_ssl is None else use_ssl

    def send(self, payload: EmailMessagePayload) -> None:
        if not self._host:
            raise ValueError("SMTP_HOST is required for sending mail.")
        if not self._from_address:
            raise ValueError("SMTP_FROM is required for sending mail.")
        if self._use_tls and self._use_ssl:
            raise ValueError("SMTP_USE_TLS and SMTP_USE_SSL cannot both be true.")

        message = EmailMessage()
        message["From"] = self._from_address
        message["To"] = payload.recipient
        message["Subject"] = payload.subject
        message.set_content(payload.body)

        if self._use_ssl:
            with smtplib.SMTP_SSL(self._host, self._port, timeout=30) as smtp:
                self._login_if_needed(smtp)
                smtp.send_message(message)
            return

        with smtplib.SMTP(self._host, self._port, timeout=30) as smtp:
            smtp.ehlo()
            if self._use_tls:
                smtp.starttls()
                smtp.ehlo()
            self._login_if_needed(smtp)
            smtp.send_message(message)

    def _login_if_needed(self, smtp: smtplib.SMTP) -> None:
        if self._username:
            smtp.login(self._username, self._password)
