import logging
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.app_settings import AppSettings
from app.db.models.message import Message
from app.llm.factory import build_chat_provider
from app.llm.types import ChatMessage, ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是用户在飞书中的私人助手。"
    "默认使用简洁中文回答，直接回答问题，不要暴露系统实现细节。"
)


@dataclass(frozen=True)
class LLMRuntimeConfig:
    provider: str
    model: str
    context_messages: int


class LLMService:
    def get_runtime_config(self, session: Session) -> LLMRuntimeConfig:
        app_settings = session.get(AppSettings, 1)
        provider = settings.default_llm_provider
        model = settings.default_llm_model
        context_messages = settings.chat_context_messages

        if app_settings is not None:
            if app_settings.default_llm_provider:
                provider = app_settings.default_llm_provider
            if app_settings.default_llm_model:
                model = app_settings.default_llm_model
            if app_settings.chat_context_messages:
                context_messages = app_settings.chat_context_messages

        return LLMRuntimeConfig(
            provider=provider.strip().lower(),
            model=model.strip(),
            context_messages=max(1, context_messages),
        )

    def generate_reply_for_user(self, session: Session, user_id: UUID) -> ChatResponse:
        runtime_config = self.get_runtime_config(session)
        provider = build_chat_provider(runtime_config.provider)
        request = ChatRequest(
            model=runtime_config.model,
            messages=self._build_messages(session, user_id, runtime_config.context_messages),
        )
        started_at = perf_counter()

        try:
            response = provider.generate(request)
        except Exception:
            latency_ms = int((perf_counter() - started_at) * 1000)
            logger.exception(
                "llm request failed: provider=%s model=%s latency_ms=%s user_id=%s",
                runtime_config.provider,
                runtime_config.model,
                latency_ms,
                user_id,
                extra={
                    "provider": runtime_config.provider,
                    "model": runtime_config.model,
                    "user_id": str(user_id),
                    "latency_ms": latency_ms,
                },
            )
            raise

        logger.info(
            "llm request completed: provider=%s model=%s latency_ms=%s user_id=%s",
            response.provider,
            response.model,
            response.latency_ms,
            user_id,
            extra={
                "provider": response.provider,
                "model": response.model,
                "user_id": str(user_id),
                "latency_ms": response.latency_ms,
            },
        )
        return response

    def _build_messages(self, session: Session, user_id: UUID, limit: int) -> list[ChatMessage]:
        records = (
            session.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        records.reverse()

        messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        for record in records:
            text = _extract_text_content(record.content)
            if not text:
                continue
            if record.role not in {"user", "assistant", "system"}:
                continue
            messages.append(ChatMessage(role=record.role, content=text))
        return messages


def _extract_text_content(content: dict | None) -> str:
    if not isinstance(content, dict):
        return ""

    text = content.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    raw = content.get("raw")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()

    return ""
