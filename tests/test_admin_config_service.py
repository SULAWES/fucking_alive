import unittest

from app.db.session import SessionLocal
from app.llm.service import LLMService
from app.services.admin_config_service import update_settings
from tests.helpers import reset_database


class AdminConfigServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_database()

    def test_provider_switch_accepts_all_supported_values(self) -> None:
        llm_service = LLMService()
        with SessionLocal() as session:
            for provider in ("openai", "anthropic", "gemini"):
                update_settings(session, default_llm_provider=provider, default_llm_model=f"{provider}-model")
                runtime = llm_service.get_runtime_config(session)
                self.assertEqual(runtime.provider, provider)
                self.assertEqual(runtime.model, f"{provider}-model")

    def test_prompt_runtime_settings_are_persisted(self) -> None:
        llm_service = LLMService()
        with SessionLocal() as session:
            update_settings(
                session,
                chat_prompt_version="chat_v1",
                command_repair_prompt_version="command_repair_v1",
                command_repair_enabled=False,
            )
            runtime = llm_service.get_runtime_config(session)

        self.assertEqual(runtime.chat_prompt_version, "chat_v1")
        self.assertEqual(runtime.command_repair_prompt_version, "command_repair_v1")
        self.assertFalse(runtime.command_repair_enabled)


if __name__ == "__main__":
    unittest.main()
