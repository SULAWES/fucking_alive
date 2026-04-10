import unittest
from types import SimpleNamespace

from app.db.models.message import Message
from app.db.models.user import User
from app.db.session import SessionLocal
from app.llm import ChatResponse
from app.services.admin_config_service import update_settings
from app.services.feishu_message_service import ALIVE_TEXT, FeishuMessageService
from tests.helpers import FakeFeishuClient, build_message_event, reset_database


class FakeLLMService:
    def get_runtime_config(self, session):
        return SimpleNamespace(provider="openai", model="fake-model", context_messages=10)

    def generate_reply_for_user(self, session, user_id):
        return ChatResponse(
            provider="openai",
            model="fake-model",
            text="这是测试 LLM 回复。",
            latency_ms=12,
            raw=None,
        )


class PlaceholderLLMService:
    def get_runtime_config(self, session):
        return SimpleNamespace(provider="gemini", model="placeholder-model", context_messages=10)

    def generate_reply_for_user(self, session, user_id):
        raise NotImplementedError("placeholder")


class FeishuMessageServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_database()

    def test_duplicate_delivery_is_deduplicated(self) -> None:
        client = FakeFeishuClient()
        service = FeishuMessageService(client, llm_service=FakeLLMService())
        event = build_message_event("om_dup_001", "hello")

        service.handle_message_receive(event)
        service.handle_message_receive(event)

        with SessionLocal() as session:
            messages = session.query(Message).all()
            self.assertEqual(len(messages), 2)
            self.assertEqual(len(client.reply_api.calls), 1)

    def test_alive_command_resets_status_without_llm(self) -> None:
        client = FakeFeishuClient()
        service = FeishuMessageService(client, llm_service=FakeLLMService())

        with SessionLocal() as session:
            user = User(feishu_user_id="ou_alive_user", timezone="Asia/Shanghai", status="ALERTED", last_seen_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
            session.add(user)
            session.commit()

        service.handle_message_receive(build_message_event("om_alive_001", "/alive", sender_id="ou_alive_user"))

        with SessionLocal() as session:
            user = session.query(User).filter(User.feishu_user_id == "ou_alive_user").one()
            assistant = (
                session.query(Message)
                .filter(Message.user_id == user.id, Message.role == "assistant")
                .order_by(Message.created_at.desc())
                .first()
            )
            self.assertEqual(user.status, "ACTIVE")
            self.assertEqual(assistant.content["text"], ALIVE_TEXT)
            self.assertIsNone(assistant.provider)

    def test_help_differs_for_admin_and_non_admin(self) -> None:
        with SessionLocal() as session:
            update_settings(session, admin_feishu_user_id="ou_admin_user")

        admin_client = FakeFeishuClient()
        admin_service = FeishuMessageService(admin_client, llm_service=FakeLLMService())
        admin_service.handle_message_receive(build_message_event("om_help_admin", "/help", sender_id="ou_admin_user"))

        non_admin_client = FakeFeishuClient()
        non_admin_service = FeishuMessageService(non_admin_client, llm_service=FakeLLMService())
        non_admin_service.handle_message_receive(build_message_event("om_help_non_admin", "/help", sender_id="ou_non_admin"))

        with SessionLocal() as session:
            admin_user = session.query(User).filter(User.feishu_user_id == "ou_admin_user").one()
            non_admin_user = session.query(User).filter(User.feishu_user_id == "ou_non_admin").one()
            admin_reply = (
                session.query(Message)
                .filter(Message.user_id == admin_user.id, Message.role == "assistant")
                .order_by(Message.created_at.desc())
                .first()
            )
            non_admin_reply = (
                session.query(Message)
                .filter(Message.user_id == non_admin_user.id, Message.role == "assistant")
                .order_by(Message.created_at.desc())
                .first()
            )
            self.assertIn("/contacts list", admin_reply.content["text"])
            self.assertNotIn("/contacts list", non_admin_reply.content["text"])

    def test_provider_switch_to_placeholder_is_visible(self) -> None:
        client = FakeFeishuClient()
        service = FeishuMessageService(client, llm_service=PlaceholderLLMService())
        service.handle_message_receive(build_message_event("om_provider_001", "ordinary text", sender_id="ou_provider"))

        with SessionLocal() as session:
            user = session.query(User).filter(User.feishu_user_id == "ou_provider").one()
            assistant = (
                session.query(Message)
                .filter(Message.user_id == user.id, Message.role == "assistant")
                .order_by(Message.created_at.desc())
                .first()
            )
            self.assertEqual(assistant.provider, "gemini")
            self.assertEqual(assistant.model, "placeholder-model")
            self.assertIn("占位实现", assistant.content["text"])


if __name__ == "__main__":
    unittest.main()
