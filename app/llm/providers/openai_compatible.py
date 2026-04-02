from time import perf_counter

import httpx

from app.llm.types import ChatRequest, ChatResponse


class OpenAICompatibleChatProvider:
    provider_name = "openai"

    def __init__(self, api_key: str, base_url: str, timeout_seconds: float = 30.0) -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY is required for the OpenAI-compatible provider.")
        if not base_url.strip():
            raise ValueError("OPENAI_BASE_URL is required for the OpenAI-compatible provider.")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def generate(self, request: ChatRequest) -> ChatResponse:
        payload = {
            "model": request.model,
            "messages": [{"role": message.role, "content": message.content} for message in request.messages],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        start = perf_counter()
        response = httpx.post(
            f"{self._base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=self._timeout_seconds,
        )
        latency_ms = int((perf_counter() - start) * 1000)
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("OpenAI-compatible response did not contain choices.")

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            raise ValueError("OpenAI-compatible response did not contain a message object.")

        text = _extract_message_text(message.get("content"))
        if not text:
            raise ValueError("OpenAI-compatible response message content was empty.")

        response_model = data.get("model") if isinstance(data.get("model"), str) else request.model
        return ChatResponse(
            provider=self.provider_name,
            model=response_model,
            text=text,
            latency_ms=latency_ms,
            raw=data,
        )


def _extract_message_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") not in {"text", "output_text"}:
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()

    return ""
