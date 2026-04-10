import unittest
from uuid import uuid4

from app.db.models.message import Message
from app.db.models.user import User
from app.db.session import SessionLocal
from app.llm.service import LLMService
from app.llm.types import ChatResponse
from app.services.admin_config_service import update_settings
from tests.helpers import reset_database


class FakeProvider:
    def __init__(self) -> None:
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return ChatResponse(
            provider="openai",
            model=request.model,
            scenario=request.scenario,
            prompt_version=request.prompt_version,
            text="ok",
            latency_ms=1,
            raw=None,
        )


class LLMServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_database()

    def test_chat_prompt_version_switch_is_applied(self) -> None:
        service = LLMService()
        provider = FakeProvider()

        with SessionLocal() as session:
            user = User(feishu_user_id="ou_prompt_chat", timezone="Asia/Shanghai", status="ACTIVE", last_seen_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
            session.add(user)
            session.flush()
            session.add(Message(user_id=user.id, provider=None, model=None, role="user", content={"text": "你好"}))
            update_settings(session, chat_prompt_version="chat_v1")

            import app.llm.service as service_module

            original_builder = service_module.build_chat_provider
            service_module.build_chat_provider = lambda provider_name: provider
            try:
                response = service.generate_reply_for_user(session, user.id, scenario="chat")
            finally:
                service_module.build_chat_provider = original_builder

        self.assertEqual(response.prompt_version, "chat_v1")
        self.assertEqual(
            provider.requests[0].messages[0].content,
            "你是用户在飞书中的私人助手。默认使用简洁中文回答，直接回答问题，不要暴露系统实现细节。"
            "只输出纯文本，不要使用 Markdown、代码块、标题或列表格式。",
        )

    def test_command_repair_disabled_falls_back_to_chat_prompt(self) -> None:
        service = LLMService()
        provider = FakeProvider()

        with SessionLocal() as session:
            user = User(feishu_user_id="ou_prompt_repair", timezone="Asia/Shanghai", status="ACTIVE", last_seen_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
            session.add(user)
            session.flush()
            session.add(Message(user_id=user.id, provider=None, model=None, role="user", content={"text": "/contact list"}))
            update_settings(session, chat_prompt_version="chat_v1", command_repair_enabled=False)

            import app.llm.service as service_module

            original_builder = service_module.build_chat_provider
            service_module.build_chat_provider = lambda provider_name: provider
            try:
                response = service.generate_reply_for_user(session, user.id, scenario="command_repair")
            finally:
                service_module.build_chat_provider = original_builder

        self.assertEqual(response.scenario, "chat")
        self.assertEqual(response.prompt_version, "chat_v1")
        self.assertEqual(provider.requests[0].scenario, "chat")

    def test_command_repair_prompt_includes_few_shot_examples(self) -> None:
        service = LLMService()
        provider = FakeProvider()

        with SessionLocal() as session:
            user = User(feishu_user_id="ou_prompt_examples", timezone="Asia/Shanghai", status="ACTIVE", last_seen_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
            session.add(user)
            session.flush()
            session.add(Message(user_id=user.id, provider=None, model=None, role="user", content={"text": "/contact list"}))
            session.commit()

            import app.llm.service as service_module

            original_builder = service_module.build_chat_provider
            service_module.build_chat_provider = lambda provider_name: provider
            try:
                response = service.generate_reply_for_user(session, user.id, scenario="command_repair")
            finally:
                service_module.build_chat_provider = original_builder

        self.assertEqual(response.scenario, "command_repair")
        self.assertEqual(response.prompt_version, "command_repair_v1")
        request = provider.requests[0]
        self.assertEqual(request.messages[1].role, "user")
        self.assertEqual(request.messages[1].content, "/contact list")
        self.assertEqual(request.messages[2].role, "assistant")
        self.assertIn("/contacts list", request.messages[2].content)


if __name__ == "__main__":
    unittest.main()
