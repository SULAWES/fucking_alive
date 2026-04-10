import unittest

from app.llm.prompt_regression import list_prompt_regression_cases
from app.llm.prompts import CHAT_PROMPT, COMMAND_REPAIR_PROMPT, get_prompt_definition, get_supported_prompt_versions


class PromptRegressionTests(unittest.TestCase):
    def test_prompt_versions_are_resolvable(self) -> None:
        self.assertEqual(get_prompt_definition("chat", "chat_v1").version, "chat_v1")
        self.assertEqual(get_prompt_definition("chat").version, "chat_v2")
        self.assertEqual(get_prompt_definition("command_repair").version, "command_repair_v1")

    def test_supported_prompt_versions_are_listed(self) -> None:
        self.assertEqual(get_supported_prompt_versions("chat"), ("chat_v1", "chat_v2"))
        self.assertEqual(get_supported_prompt_versions("command_repair"), ("command_repair_v1",))

    def test_chat_prompt_contains_required_guards(self) -> None:
        prompt = CHAT_PROMPT.system_prompt
        self.assertIn("简洁中文", prompt)
        self.assertIn("不要暴露系统实现细节", prompt)
        self.assertIn("不要伪造系统状态", prompt)
        self.assertIn("不要声称已经发邮件", prompt)
        self.assertIn("只输出纯文本", prompt)

    def test_command_repair_prompt_contains_required_guards(self) -> None:
        prompt = COMMAND_REPAIR_PROMPT.system_prompt
        self.assertIn("命令纠错助手", prompt)
        self.assertIn("正确命令", prompt)
        self.assertIn("不要编造不存在的命令", prompt)
        self.assertIn("/help", prompt)
        self.assertIn("只输出纯文本", prompt)
        self.assertGreaterEqual(len(COMMAND_REPAIR_PROMPT.few_shot_messages), 2)

    def test_prompt_regression_cases_cover_both_scenarios(self) -> None:
        cases = list_prompt_regression_cases()
        scenarios = {case.scenario for case in cases}
        self.assertIn("chat", scenarios)
        self.assertIn("command_repair", scenarios)
        self.assertGreaterEqual(len(cases), 4)

    def test_regression_cases_have_signals_and_notes(self) -> None:
        for case in list_prompt_regression_cases():
            self.assertTrue(case.expected_signals)
            self.assertTrue(case.note.strip())
            if case.scenario == "command_repair":
                self.assertTrue(case.user_input.startswith("/"))


if __name__ == "__main__":
    unittest.main()
