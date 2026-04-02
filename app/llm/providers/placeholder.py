from app.llm.types import ChatRequest, ChatResponse


class PlaceholderChatProvider:
    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def generate(self, request: ChatRequest) -> ChatResponse:
        raise NotImplementedError(f"{self.provider_name} provider is still a placeholder in phase 3.")
