from app.core.config import settings
from app.llm.providers.base import ChatProvider
from app.llm.providers.openai_compatible import OpenAICompatibleChatProvider
from app.llm.providers.placeholder import PlaceholderChatProvider


def build_chat_provider(provider_name: str) -> ChatProvider:
    normalized = provider_name.strip().lower()

    if normalized == "openai":
        return OpenAICompatibleChatProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    if normalized == "anthropic":
        return PlaceholderChatProvider("anthropic")
    if normalized == "gemini":
        return PlaceholderChatProvider("gemini")

    raise ValueError(f"Unsupported LLM provider: {provider_name}")
