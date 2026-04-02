import json
import logging
import uuid
from datetime import datetime, timezone

import lark_oapi as lark
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.message import Message
from app.db.models.user import User
from app.db.session import SessionLocal
from app.llm import LLMService

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "可用命令：\n"
    "/help 查看帮助\n"
    "/alive 手动报平安\n\n"
    "当前阶段已接入 OpenAI 兼容格式对话。\n"
    "Anthropic / Gemini 适配器仍为占位。"
)

ALIVE_TEXT = "已记录本次存活心跳，72 小时计时已重置。"
UNSUPPORTED_TEXT = "当前阶段仅支持文本消息。"
LLM_FAILURE_TEXT = "暂时无法获取模型回复，请稍后再试。"
PROVIDER_PLACEHOLDER_TEXT = "当前 provider（{provider}）仍为占位实现，尚未接入真实调用。"


class FeishuMessageService:
    def __init__(self, client: lark.Client, llm_service: LLMService | None = None) -> None:
        self._client = client
        self._llm_service = llm_service or LLMService()

    def handle_message_receive(self, data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        event = data.event
        if event is None or event.message is None or event.sender is None:
            logger.warning("skip feishu event without message or sender")
            return

        message = event.message
        sender = event.sender
        if message.chat_type != "p2p":
            logger.info("skip non-p2p message: chat_type=%s", message.chat_type)
            return

        sender_user_id = sender.sender_id.user_id if sender.sender_id else None
        sender_open_id = sender.sender_id.open_id if sender.sender_id else None
        sender_union_id = sender.sender_id.union_id if sender.sender_id else None
        canonical_sender_id = sender_open_id or sender_user_id or sender_union_id
        if not canonical_sender_id:
            logger.warning("skip feishu message without sender identifier")
            return

        parsed_content, text_content = _parse_message_content(message.content)
        now = datetime.now(timezone.utc)

        with SessionLocal() as session:
            if _message_exists(session, message.message_id):
                logger.info("skip duplicated feishu message: %s", message.message_id)
                return

            user = _get_or_create_user(session, canonical_sender_id, now)
            user.status = "ACTIVE"
            user.last_seen_at = now

            incoming_record = Message(
                user_id=user.id,
                provider=None,
                model=None,
                role="user",
                chat_id=message.chat_id,
                chat_type=message.chat_type,
                message_type=message.message_type,
                sender_user_id=sender_user_id,
                sender_open_id=sender_open_id,
                sender_union_id=sender_union_id,
                content=parsed_content,
                raw_event=_serialize_event(data),
                feishu_message_id=message.message_id,
            )
            session.add(incoming_record)

            direct_reply = _build_direct_reply(message.message_type, text_content)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                logger.info("skip duplicated feishu message on commit: %s", message.message_id)
                return

            reply_provider = None
            reply_model = None
            if direct_reply is not None:
                reply_text = direct_reply
            else:
                reply_text, reply_provider, reply_model = self._generate_llm_reply(session, user.id)

            reply_response = self._reply_text(message.message_id, reply_text)
            if reply_response is None:
                return

            assistant_record = Message(
                user_id=user.id,
                provider=reply_provider,
                model=reply_model,
                role="assistant",
                chat_id=message.chat_id,
                chat_type=message.chat_type,
                message_type="text",
                sender_user_id=None,
                sender_open_id=None,
                sender_union_id=None,
                content={"text": reply_text},
                raw_event=None,
                feishu_message_id=reply_response.data.message_id if reply_response.data else None,
            )
            session.add(assistant_record)
            session.commit()

    def _generate_llm_reply(self, session: Session, user_id) -> tuple[str, str | None, str | None]:
        runtime_config = self._llm_service.get_runtime_config(session)
        try:
            response = self._llm_service.generate_reply_for_user(session, user_id)
            return response.text, response.provider, response.model
        except NotImplementedError:
            logger.warning(
                "llm provider is still placeholder: provider=%s model=%s user_id=%s",
                runtime_config.provider,
                runtime_config.model,
                user_id,
            )
            return (
                PROVIDER_PLACEHOLDER_TEXT.format(provider=runtime_config.provider),
                runtime_config.provider,
                runtime_config.model,
            )
        except Exception:
            return LLM_FAILURE_TEXT, runtime_config.provider, runtime_config.model

    def _reply_text(self, message_id: str, text: str) -> lark.im.v1.ReplyMessageResponse | None:
        request = (
            lark.im.v1.ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                lark.im.v1.ReplyMessageRequestBody.builder()
                .content(json.dumps({"text": text}, ensure_ascii=False))
                .msg_type("text")
                .reply_in_thread(False)
                .uuid(str(uuid.uuid4()))
                .build()
            )
            .build()
        )
        response = self._client.im.v1.message.reply(request)
        if response.success():
            return response

        logger.error(
            "failed to reply feishu message: code=%s msg=%s log_id=%s",
            response.code,
            response.msg,
            response.get_log_id(),
        )
        return None


def _message_exists(session: Session, message_id: str | None) -> bool:
    if not message_id:
        return False
    return session.query(Message.id).filter(Message.feishu_message_id == message_id).first() is not None


def _get_or_create_user(session: Session, feishu_user_id: str, now: datetime) -> User:
    user = session.query(User).filter(User.feishu_user_id == feishu_user_id).one_or_none()
    if user is None:
        user = User(feishu_user_id=feishu_user_id, timezone="Asia/Shanghai", status="ACTIVE", last_seen_at=now)
        session.add(user)
        session.flush()
    return user


def _parse_message_content(raw_content: str | None) -> tuple[dict, str]:
    if not raw_content:
        return {"raw": ""}, ""
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError:
        return {"raw": raw_content}, raw_content.strip()

    if isinstance(parsed, dict):
        text = parsed.get("text", "")
        return parsed, text.strip() if isinstance(text, str) else ""

    return {"raw": raw_content}, str(parsed).strip()


def _build_direct_reply(message_type: str | None, text: str) -> str | None:
    if message_type != "text":
        return UNSUPPORTED_TEXT

    normalized = text.strip()
    if normalized == "/alive":
        return ALIVE_TEXT
    if normalized == "/help":
        return HELP_TEXT
    return None


def _serialize_event(data: lark.im.v1.P2ImMessageReceiveV1) -> dict:
    return {
        "schema": data.schema,
        "event_type": data.header.event_type if data.header else None,
        "tenant_key": data.header.tenant_key if data.header else None,
        "event": {
            "sender": {
                "sender_type": data.event.sender.sender_type if data.event and data.event.sender else None,
                "tenant_key": data.event.sender.tenant_key if data.event and data.event.sender else None,
                "sender_id": {
                    "user_id": data.event.sender.sender_id.user_id
                    if data.event and data.event.sender and data.event.sender.sender_id
                    else None,
                    "open_id": data.event.sender.sender_id.open_id
                    if data.event and data.event.sender and data.event.sender.sender_id
                    else None,
                    "union_id": data.event.sender.sender_id.union_id
                    if data.event and data.event.sender and data.event.sender.sender_id
                    else None,
                },
            },
            "message": {
                "message_id": data.event.message.message_id if data.event and data.event.message else None,
                "chat_id": data.event.message.chat_id if data.event and data.event.message else None,
                "chat_type": data.event.message.chat_type if data.event and data.event.message else None,
                "message_type": data.event.message.message_type if data.event and data.event.message else None,
                "content": data.event.message.content if data.event and data.event.message else None,
                "create_time": data.event.message.create_time if data.event and data.event.message else None,
            },
        },
    }
