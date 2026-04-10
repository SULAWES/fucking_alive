import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.alert_event import AlertEvent
from app.db.models.app_settings import AppSettings
from app.db.models.contact import Contact
from app.db.models.email_template import EmailTemplate
from app.db.models.user import User
from app.db.session import SessionLocal
from app.mail import (
    AlertTemplateContent,
    AlertTemplateVariables,
    EmailMessagePayload,
    MailSender,
    SmtpMailSender,
    TemplateValidationError,
    format_last_seen_at,
    render_alert_template,
    validate_alert_template,
)

logger = logging.getLogger(__name__)

ALERT_EVENT_TYPE = "INACTIVITY_ALERT"
ALERT_TEMPLATE_KEY = "alert_default"
DEFAULT_TEMPLATE = AlertTemplateContent(
    subject="长时间未联系提醒：{user_name}",
    body=(
        "你好，{contact_name}。\n\n"
        "系统检测到 {user_name} 已连续 {inactive_hours} 小时未通过飞书与机器人互动。\n"
        "最后一次记录时间：{last_seen_at}。\n\n"
        "这是一条自动提醒消息，仅用于提示你主动确认对方近况，并不代表系统已确认异常。"
    ),
)


@dataclass(frozen=True)
class AlertScanResult:
    scanned_users: int = 0
    overdue_users: int = 0
    delivered: int = 0
    failed: int = 0
    skipped: int = 0


class AlertingService:
    def __init__(self, mail_sender: MailSender | None = None) -> None:
        self._mail_sender = mail_sender or SmtpMailSender()

    def run_scan_once(self, now: datetime | None = None) -> AlertScanResult:
        effective_now = now or datetime.now(timezone.utc)
        with SessionLocal() as session:
            return self._run_scan(session, effective_now)

    def send_test_alert(
        self,
        recipients: list[str],
        subject: str,
        body: str,
    ) -> int:
        validate_alert_template(subject, body)
        for recipient in recipients:
            self._mail_sender.send(
                EmailMessagePayload(
                    recipient=recipient,
                    subject=subject,
                    body=body,
                )
            )
        return len(recipients)

    def _run_scan(self, session: Session, now: datetime) -> AlertScanResult:
        app_settings = session.get(AppSettings, 1)
        alert_hours = settings.alert_default_hours
        if app_settings is not None and app_settings.alert_default_hours:
            alert_hours = app_settings.alert_default_hours

        overdue_before = now - timedelta(hours=alert_hours)
        users = (
            session.query(User)
            .filter(User.status.in_(["ACTIVE", "ALERTED"]), User.last_seen_at <= overdue_before)
            .order_by(User.last_seen_at.asc())
            .all()
        )

        delivered = 0
        failed = 0
        skipped = 0

        for user in users:
            contacts = (
                session.query(Contact)
                .filter(Contact.user_id == user.id, Contact.enabled.is_(True))
                .order_by(Contact.priority.asc(), Contact.created_at.asc())
                .all()
            )
            if not contacts:
                logger.warning(
                    "skip overdue user without enabled contacts: user_id=%s",
                    user.id,
                    extra={"user_id": str(user.id), "event_type": ALERT_EVENT_TYPE, "delivery_status": "SKIPPED"},
                )
                skipped += 1
                continue

            template = self._get_template(session)
            user_delivered = 0
            user_failed = 0
            user_skipped = 0

            for contact in contacts:
                result = self._send_alert_for_contact(
                    session=session,
                    user=user,
                    contact=contact,
                    template=template,
                    inactive_hours=alert_hours,
                    now=now,
                )
                if result == "SENT":
                    user_delivered += 1
                elif result == "FAILED":
                    user_failed += 1
                else:
                    user_skipped += 1

            if user_delivered or user_failed or user.status != "ALERTED":
                user.status = "ALERTED"
                session.add(user)
                session.commit()

            delivered += user_delivered
            failed += user_failed
            skipped += user_skipped

        return AlertScanResult(
            scanned_users=session.query(User.id).count(),
            overdue_users=len(users),
            delivered=delivered,
            failed=failed,
            skipped=skipped,
        )

    def _get_template(self, session: Session) -> AlertTemplateContent:
        record = (
            session.query(EmailTemplate)
            .filter(EmailTemplate.template_key == ALERT_TEMPLATE_KEY, EmailTemplate.is_active.is_(True))
            .one_or_none()
        )
        if record is None:
            return DEFAULT_TEMPLATE

        try:
            validate_alert_template(record.subject, record.body)
        except TemplateValidationError:
            logger.exception("invalid alert template in database, falling back to default: template_key=%s", ALERT_TEMPLATE_KEY)
            return DEFAULT_TEMPLATE

        return AlertTemplateContent(subject=record.subject, body=record.body)

    def _send_alert_for_contact(
        self,
        session: Session,
        user: User,
        contact: Contact,
        template: AlertTemplateContent,
        inactive_hours: int,
        now: datetime,
    ) -> str:
        dedupe_key = _build_dedupe_key(user, contact)
        event = session.query(AlertEvent).filter(AlertEvent.dedupe_key == dedupe_key).one_or_none()
        if event is not None and event.delivery_status == "SENT":
            return "SKIPPED"

        rendered = render_alert_template(
            template,
            AlertTemplateVariables(
                user_name=user.display_name or user.feishu_user_id,
                last_seen_at=format_last_seen_at(user.last_seen_at),
                inactive_hours=inactive_hours,
                contact_name=contact.name,
            ),
        )

        if event is None:
            event = AlertEvent(
                user_id=user.id,
                contact_id=contact.id,
                event_type=ALERT_EVENT_TYPE,
                dedupe_key=dedupe_key,
            )
            session.add(event)

        event.subject = rendered.subject
        event.body = rendered.body
        event.triggered_at = now
        event.delivery_status = "PENDING"
        event.error_message = None
        session.flush()

        try:
            self._mail_sender.send(
                EmailMessagePayload(
                    recipient=contact.email,
                    subject=rendered.subject,
                    body=rendered.body,
                )
            )
        except Exception as exc:
            session.rollback()
            event = session.query(AlertEvent).filter(AlertEvent.dedupe_key == dedupe_key).one_or_none()
            if event is None:
                event = AlertEvent(
                    user_id=user.id,
                    contact_id=contact.id,
                    event_type=ALERT_EVENT_TYPE,
                    dedupe_key=dedupe_key,
                )
                session.add(event)
            event.subject = rendered.subject
            event.body = rendered.body
            event.triggered_at = now
            event.delivery_status = "FAILED"
            event.error_message = str(exc)
            session.commit()
            logger.exception(
                "failed to send inactivity alert: user_id=%s contact_id=%s email=%s",
                user.id,
                contact.id,
                contact.email,
                extra={
                    "user_id": str(user.id),
                    "contact_id": str(contact.id),
                    "event_type": ALERT_EVENT_TYPE,
                    "delivery_status": "FAILED",
                },
            )
            return "FAILED"

        event.delivery_status = "SENT"
        event.error_message = None
        session.commit()
        logger.info(
            "sent inactivity alert: user_id=%s contact_id=%s email=%s",
            user.id,
            contact.id,
            contact.email,
            extra={
                "user_id": str(user.id),
                "contact_id": str(contact.id),
                "event_type": ALERT_EVENT_TYPE,
                "delivery_status": "SENT",
            },
        )
        return "SENT"


def _build_dedupe_key(user: User, contact: Contact) -> str:
    return f"alert:{user.id}:{contact.id}:{int(user.last_seen_at.timestamp())}"
