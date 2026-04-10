import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.db.models.message import Message
from app.db.models.user import User
from app.db.session import SessionLocal, SessionLocal as RealSessionLocal
from app.llm import ChatResponse
from app.services.admin_config_service import update_settings
from app.services.feishu_message_service import ALIVE_TEXT, AssistantMessagePayload, FeishuMessageService
from tests.helpers import FakeFeishuClient, build_message_event, reset_database


class FakeLLMService:
    def __init__(self, *, command_repair_enabled: bool = True) -> None:
        self.scenarios: list[str] = []
        self.command_repair_enabled = command_repair_enabled

    def get_runtime_config(self, session):
        return SimpleNamespace(
            provider="openai",
            model="fake-model",
            context_messages=10,
            chat_prompt_version="chat_v2",
            command_repair_prompt_version="command_repair_v1",
            command_repair_enabled=self.command_repair_enabled,
        )

    def generate_reply_for_user(self, session, user_id, *, scenario="chat"):
        self.scenarios.append(scenario)
        return ChatResponse(
            provider="openai",
            model="fake-model",
            scenario=scenario,
            prompt_version="test_prompt_v1",
            text="这是测试 LLM 回复。",
            latency_ms=12,
            raw=None,
        )


class PlaceholderLLMService:
    def get_runtime_config(self, session):
        return SimpleNamespace(
            provider="gemini",
            model="placeholder-model",
            context_messages=10,
            chat_prompt_version="chat_v2",
            command_repair_prompt_version="command_repair_v1",
            command_repair_enabled=True,
        )

    def generate_reply_for_user(self, session, user_id, *, scenario="chat"):
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

    def test_unknown_slash_command_uses_command_repair_scenario(self) -> None:
        fake_llm = FakeLLMService()
        client = FakeFeishuClient()
        service = FeishuMessageService(client, llm_service=fake_llm)
        service.handle_message_receive(build_message_event("om_slash_unknown", "/contact list", sender_id="ou_slash"))

        self.assertEqual(fake_llm.scenarios, ["command_repair"])

    def test_unknown_slash_command_falls_back_to_chat_when_command_repair_disabled(self) -> None:
        fake_llm = FakeLLMService(command_repair_enabled=False)
        client = FakeFeishuClient()
        service = FeishuMessageService(client, llm_service=fake_llm)

        with SessionLocal() as session:
            update_settings(session, command_repair_enabled=False)

        service.handle_message_receive(build_message_event("om_slash_chat", "/contact list", sender_id="ou_slash_chat"))

        self.assertEqual(fake_llm.scenarios, ["chat"])

    def test_assistant_message_persistence_retries_with_fresh_session(self) -> None:
        client = FakeFeishuClient()
        service = FeishuMessageService(client, llm_service=FakeLLMService())

        with SessionLocal() as session:
            user = User(
                feishu_user_id="ou_retry_user",
                timezone="Asia/Shanghai",
                status="ACTIVE",
                last_seen_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
            session.add(user)
            session.commit()
            user_id = user.id

        payload = AssistantMessagePayload(
            user_id=user_id,
            provider="openai",
            model="fake-model",
            role="assistant",
            chat_id="chat-retry",
            chat_type="p2p",
            message_type="text",
            sender_user_id=None,
            sender_open_id=None,
            sender_union_id=None,
            content={"text": "retry assistant reply"},
            raw_event=None,
            feishu_message_id="om_retry_assistant",
        )

        class FailingSession:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def add(self, _obj):
                return None

            def commit(self):
                raise RuntimeError("transient commit failure")

        class SessionFactory:
            def __init__(self):
                self.calls = 0

            def __call__(self):
                self.calls += 1
                if self.calls == 1:
                    return FailingSession()
                return RealSessionLocal()

        factory = SessionFactory()
        with patch("app.services.feishu_message_service.SessionLocal", factory):
            service._persist_assistant_message(payload)

        with SessionLocal() as session:
            records = session.query(Message).filter(Message.feishu_message_id == "om_retry_assistant").all()
            self.assertEqual(len(records), 1)


if __name__ == "__main__":
    unittest.main()
