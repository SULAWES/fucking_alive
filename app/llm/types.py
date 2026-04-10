from dataclasses import dataclass


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatRequest:
    model: str
    scenario: str
    prompt_version: str
    messages: list[ChatMessage]


@dataclass(frozen=True)
class ChatResponse:
    provider: str
    model: str
    scenario: str
    prompt_version: str
    text: str
    latency_ms: int
    raw: dict | None = None
