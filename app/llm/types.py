from dataclasses import dataclass


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatRequest:
    model: str
    messages: list[ChatMessage]


@dataclass(frozen=True)
class ChatResponse:
    provider: str
    model: str
    text: str
    latency_ms: int
    raw: dict | None = None
