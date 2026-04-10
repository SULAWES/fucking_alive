import unittest
from datetime import datetime, timedelta, timezone

from app.alerts.service import AlertingService
from app.db.models.alert_event import AlertEvent
from app.db.models.contact import Contact
from app.db.models.user import User
from app.db.session import SessionLocal
from app.mail.template import TemplateValidationError, validate_alert_template
from tests.helpers import FakeMailSender, reset_database


class AlertingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_database()

    def test_alert_timeout_dedupe_and_recovery_cycle(self) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as session:
            user = User(
                feishu_user_id="ou_alert_user",
                display_name="Alert User",
                timezone="Asia/Shanghai",
                status="ACTIVE",
                last_seen_at=now - timedelta(hours=80),
            )
            session.add(user)
            session.flush()
            session.add(Contact(user_id=user.id, name="Alice", email="alice@example.com", relation="friend", priority=1, enabled=True))
            session.commit()

        fake_sender = FakeMailSender()
        service = AlertingService(mail_sender=fake_sender)
        first = service.run_scan_once(now=now)
        second = service.run_scan_once(now=now)

        with SessionLocal() as session:
            user = session.query(User).filter(User.feishu_user_id == "ou_alert_user").one()
            events = session.query(AlertEvent).filter(AlertEvent.user_id == user.id).all()
            self.assertEqual(first.delivered, 1)
            self.assertEqual(second.delivered, 0)
            self.assertEqual(second.skipped, 1)
            self.assertEqual(user.status, "ALERTED")
            self.assertEqual(len(events), 1)

            user.status = "ACTIVE"
            user.last_seen_at = now + timedelta(hours=1)
            session.add(user)
            session.commit()

        third = service.run_scan_once(now=now + timedelta(hours=82))
        with SessionLocal() as session:
            user = session.query(User).filter(User.feishu_user_id == "ou_alert_user").one()
            events = session.query(AlertEvent).filter(AlertEvent.user_id == user.id).all()
            self.assertEqual(third.delivered, 1)
            self.assertEqual(user.status, "ALERTED")
            self.assertEqual(len(events), 2)

    def test_template_variable_validation_rejects_unknown_key(self) -> None:
        with self.assertRaises(TemplateValidationError):
            validate_alert_template("bad {unknown}", "body {unknown}")


if __name__ == "__main__":
    unittest.main()
