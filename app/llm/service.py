import logging
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.app_settings import AppSettings
from app.db.models.message import Message
from app.llm.factory import build_chat_provider
from app.llm.prompts import get_prompt_definition
from app.llm.types import ChatMessage, ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMRuntimeConfig:
    provider: str
    model: str
    context_messages: int
    chat_prompt_version: str
    command_repair_prompt_version: str
    command_repair_enabled: bool


class LLMService:
    def get_runtime_config(self, session: Session) -> LLMRuntimeConfig:
        app_settings = session.get(AppSettings, 1)
        provider = settings.default_llm_provider
        model = settings.default_llm_model
        context_messages = settings.chat_context_messages
        chat_prompt_version = settings.chat_prompt_version
        command_repair_prompt_version = settings.command_repair_prompt_version
        command_repair_enabled = settings.command_repair_enabled

        if app_settings is not None:
            if app_settings.default_llm_provider:
                provider = app_settings.default_llm_provider
            if app_settings.default_llm_model:
                model = app_settings.default_llm_model
            if app_settings.chat_context_messages:
                context_messages = app_settings.chat_context_messages
            if app_settings.chat_prompt_version:
                chat_prompt_version = app_settings.chat_prompt_version
            if app_settings.command_repair_prompt_version:
                command_repair_prompt_version = app_settings.command_repair_prompt_version
            command_repair_enabled = app_settings.command_repair_enabled

        return LLMRuntimeConfig(
            provider=provider.strip().lower(),
            model=model.strip(),
            context_messages=max(1, context_messages),
            chat_prompt_version=chat_prompt_version.strip().lower(),
            command_repair_prompt_version=command_repair_prompt_version.strip().lower(),
            command_repair_enabled=bool(command_repair_enabled),
        )

    def generate_reply_for_user(self, session: Session, user_id: UUID, *, scenario: str = "chat") -> ChatResponse:
        runtime_config = self.get_runtime_config(session)
        prompt = self._resolve_prompt(runtime_config, scenario)
        provider = build_chat_provider(runtime_config.provider)
        request = ChatRequest(
            model=runtime_config.model,
            scenario=prompt.scenario,
            prompt_version=prompt.version,
            messages=self._build_messages(
                session,
                user_id,
                runtime_config.context_messages,
                system_prompt=prompt.system_prompt,
                few_shot_messages=prompt.few_shot_messages,
            ),
        )
        started_at = perf_counter()

        try:
            response = provider.generate(request)
        except Exception:
            latency_ms = int((perf_counter() - started_at) * 1000)
            logger.exception(
                "llm request failed: provider=%s model=%s prompt_version=%s latency_ms=%s user_id=%s",
                runtime_config.provider,
                runtime_config.model,
                prompt.version,
                latency_ms,
                user_id,
                extra={
                    "provider": runtime_config.provider,
                    "model": runtime_config.model,
                    "scenario": prompt.scenario,
                    "user_id": str(user_id),
                    "latency_ms": latency_ms,
                    "prompt_version": prompt.version,
                },
            )
            raise

        logger.info(
            "llm request completed: provider=%s model=%s prompt_version=%s latency_ms=%s user_id=%s",
            response.provider,
            response.model,
            response.prompt_version,
            response.latency_ms,
            user_id,
            extra={
                "provider": response.provider,
                "model": response.model,
                "scenario": response.scenario,
                "user_id": str(user_id),
                "latency_ms": response.latency_ms,
                "prompt_version": response.prompt_version,
            },
        )
        return response

    def _resolve_prompt(self, runtime_config: LLMRuntimeConfig, scenario: str):
        normalized = scenario.strip().lower()
        if normalized == "command_repair" and runtime_config.command_repair_enabled:
            return get_prompt_definition("command_repair", runtime_config.command_repair_prompt_version)
        return get_prompt_definition("chat", runtime_config.chat_prompt_version)

    def _build_messages(
        self,
        session: Session,
        user_id: UUID,
        limit: int,
        *,
        system_prompt: str,
        few_shot_messages: tuple[tuple[str, str], ...] = (),
    ) -> list[ChatMessage]:
        records = (
            session.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        records.reverse()

        messages = [ChatMessage(role="system", content=system_prompt)]
        for role, content in few_shot_messages:
            messages.append(ChatMessage(role=role, content=content))
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
