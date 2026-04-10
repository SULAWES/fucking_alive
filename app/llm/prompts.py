from dataclasses import dataclass


@dataclass(frozen=True)
class PromptDefinition:
    scenario: str
    version: str
    system_prompt: str
    few_shot_messages: tuple[tuple[str, str], ...] = ()


CHAT_PROMPT_V1 = PromptDefinition(
    scenario="chat",
    version="chat_v1",
    system_prompt=(
        "你是用户在飞书中的私人助手。"
        "默认使用简洁中文回答，直接回答问题，不要暴露系统实现细节。"
        "只输出纯文本，不要使用 Markdown、代码块、标题或列表格式。"
    ),
)

CHAT_PROMPT_V2 = PromptDefinition(
    scenario="chat",
    version="chat_v2",
    system_prompt=(
        "你是用户在飞书中的私人助手。"
        "默认使用简洁中文回答，优先直接回答问题，不要空话。"
        "不要暴露系统实现细节。"
        "不要伪造系统状态，不要声称已经发邮件、已经报警、已经修改配置，"
        "除非当前上下文里明确展示这些动作刚刚发生。"
        "只输出纯文本，不要使用 Markdown、代码块、标题或列表格式。"
    ),
)

COMMAND_REPAIR_PROMPT_V1 = PromptDefinition(
    scenario="command_repair",
    version="command_repair_v1",
    system_prompt=(
        "你是飞书机器人里的命令纠错助手。"
        "当用户输入看起来像斜杠命令但未被系统识别时，"
        "你要优先猜测最可能的正确命令，并用简洁中文给出修正建议。"
        "不要编造不存在的命令，不要假装系统已经执行成功。"
        "如果无法确定，明确说明无法判断，并建议用户发送 /help 查看可用命令。"
        "只输出纯文本，不要使用 Markdown、代码块、标题或列表格式。"
    ),
    few_shot_messages=(
        ("user", "/contact list"),
        ("assistant", "如果你是想查看联系人列表，请使用 /contacts list。若不确定，可发送 /help 查看可用命令。"),
        ("user", "/templte show"),
        ("assistant", "如果你是想查看当前邮件模板，请使用 /template show。若不确定，可发送 /help 查看可用命令。"),
    ),
)

CHAT_PROMPT = CHAT_PROMPT_V2
COMMAND_REPAIR_PROMPT = COMMAND_REPAIR_PROMPT_V1

PROMPT_REGISTRY: dict[str, dict[str, PromptDefinition]] = {
    "chat": {
        CHAT_PROMPT_V1.version: CHAT_PROMPT_V1,
        CHAT_PROMPT_V2.version: CHAT_PROMPT_V2,
    },
    "command_repair": {
        COMMAND_REPAIR_PROMPT_V1.version: COMMAND_REPAIR_PROMPT_V1,
    },
}

DEFAULT_PROMPT_VERSIONS = {
    "chat": CHAT_PROMPT_V2.version,
    "command_repair": COMMAND_REPAIR_PROMPT_V1.version,
}


def get_prompt_definition(scenario: str, version: str | None = None) -> PromptDefinition:
    normalized = scenario.strip().lower()
    if normalized not in PROMPT_REGISTRY:
        normalized = "chat"

    resolved_version = (version or DEFAULT_PROMPT_VERSIONS[normalized]).strip().lower()
    return PROMPT_REGISTRY[normalized].get(resolved_version) or PROMPT_REGISTRY[normalized][
        DEFAULT_PROMPT_VERSIONS[normalized]
    ]


def get_supported_prompt_versions(scenario: str) -> tuple[str, ...]:
    normalized = scenario.strip().lower()
    if normalized not in PROMPT_REGISTRY:
        normalized = "chat"
    return tuple(PROMPT_REGISTRY[normalized].keys())
