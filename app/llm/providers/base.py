from typing import Protocol

from app.llm.types import ChatRequest, ChatResponse


class ChatProvider(Protocol):
    provider_name: str

    def generate(self, request: ChatRequest) -> ChatResponse:
        ...
