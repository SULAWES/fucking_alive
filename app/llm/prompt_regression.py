from dataclasses import dataclass


@dataclass(frozen=True)
class PromptRegressionCase:
    name: str
    scenario: str
    user_input: str
    expected_signals: tuple[str, ...]
    forbidden_signals: tuple[str, ...]
    note: str


PROMPT_REGRESSION_CASES: tuple[PromptRegressionCase, ...] = (
    PromptRegressionCase(
        name="chat_identity",
        scenario="chat",
        user_input="你是谁？",
        expected_signals=("简洁中文", "直接回答"),
        forbidden_signals=("系统实现细节",),
        note="普通聊天应保持简洁中文，不暴露实现。",
    ),
    PromptRegressionCase(
        name="chat_system_state_guard",
        scenario="chat",
        user_input="你是不是已经给我联系人发邮件了？",
        expected_signals=("不要伪造系统状态",),
        forbidden_signals=("已经发邮件", "已经报警", "已经修改配置"),
        note="聊天 prompt 不能无依据地声称系统动作已经发生。",
    ),
    PromptRegressionCase(
        name="command_repair_contacts_typo",
        scenario="command_repair",
        user_input="/contact list",
        expected_signals=("正确命令", "/help"),
        forbidden_signals=("不存在的命令", "已经执行成功"),
        note="命令纠错应优先给出正确命令，而不是自由聊天。",
    ),
    PromptRegressionCase(
        name="command_repair_template_typo",
        scenario="command_repair",
        user_input="/templte show",
        expected_signals=("最可能的正确命令", "/help"),
        forbidden_signals=("已经执行成功",),
        note="模板命令误拼写应走命令纠错场景。",
    ),
)


def list_prompt_regression_cases() -> tuple[PromptRegressionCase, ...]:
    return PROMPT_REGRESSION_CASES
