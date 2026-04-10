import unittest
from datetime import datetime, timedelta, timezone

from app.db.models.pending_admin_change import PendingAdminChange
from app.db.session import SessionLocal
from app.services.admin_config_service import get_or_create_email_template, update_settings
from app.services.feishu_admin_service import FeishuAdminService
from tests.helpers import reset_database


class FeishuAdminServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_database()
        with SessionLocal() as session:
            update_settings(session, admin_feishu_user_id="ou_admin")
        self.service = FeishuAdminService()

    def test_contact_add_confirm_and_cancel_flow(self) -> None:
        with SessionLocal() as session:
            preview = self.service.handle_command(session, "ou_admin", '/contacts add "Alice" alice@example.com friend')
            self.assertIn("/config confirm", preview)
            confirm = self.service.handle_command(session, "ou_admin", "/config confirm")
            self.assertIn("联系人变更已生效", confirm)

            update_preview = self.service.handle_command(
                session,
                "ou_admin",
                '/contacts update alice@example.com "Alice Updated" family disabled',
            )
            self.assertIn("disabled", update_preview)
            cancel = self.service.handle_command(session, "ou_admin", "/config cancel")
            self.assertEqual(cancel, "已取消当前待确认变更。")
            listing = self.service.handle_command(session, "ou_admin", "/contacts list")
            self.assertIn("Alice <alice@example.com>", listing)
            self.assertNotIn("Alice Updated", listing)

    def test_template_pending_changes_stack_before_confirm(self) -> None:
        with SessionLocal() as session:
            first = self.service.handle_command(session, "ou_admin", "/template subject set 测试：{user_name}")
            second = self.service.handle_command(session, "ou_admin", "/template body set 你好，{contact_name}。")
            self.assertIn("/config confirm", first)
            self.assertIn("/config confirm", second)
            confirm = self.service.handle_command(session, "ou_admin", "/config confirm")
            template = get_or_create_email_template(session)
            self.assertIn("模板变更已生效", confirm)
            self.assertEqual(template.subject, "测试：{user_name}")
            self.assertEqual(template.body, "你好，{contact_name}。")

    def test_expired_pending_change_is_cleaned_up(self) -> None:
        with SessionLocal() as session:
            self.service.handle_command(session, "ou_admin", '/contacts add "Alice" alice@example.com friend')
            pending = (
                session.query(PendingAdminChange)
                .filter(PendingAdminChange.admin_feishu_user_id == "ou_admin")
                .one()
            )
            pending.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            session.add(pending)
            session.commit()

            response = self.service.handle_command(session, "ou_admin", "/config confirm")
            self.assertEqual(response, "当前没有待确认的变更。")


if __name__ == "__main__":
    unittest.main()
