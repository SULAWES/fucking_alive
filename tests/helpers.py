import json
import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as app_main
from app.db.models.alert_event import AlertEvent
from app.db.models.contact import Contact
from app.db.models.email_template import EmailTemplate
from app.db.models.message import Message
from app.db.models.pending_admin_change import PendingAdminChange
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services.admin_config_service import (
    DEFAULT_TEMPLATE_BODY,
    DEFAULT_TEMPLATE_SUBJECT,
    get_or_create_app_settings,
    get_or_create_email_template,
    update_settings,
)


class FakeReplyResponse:
    def __init__(self, message_id: str) -> None:
        self.data = SimpleNamespace(message_id=message_id)
        self.code = 0
        self.msg = "ok"

    def success(self) -> bool:
        return True

    def get_log_id(self) -> str:
        return "fake-log-id"


class FakeReplyAPI:
    def __init__(self) -> None:
        self.calls = []

    def reply(self, request):
        self.calls.append(request)
        return FakeReplyResponse(message_id=f"om_fake_reply_{uuid.uuid4().hex}")


class FakeFeishuClient:
    def __init__(self) -> None:
        reply_api = FakeReplyAPI()
        self.reply_api = reply_api
        self.im = SimpleNamespace(v1=SimpleNamespace(message=reply_api))


class FakeMailSender:
    def __init__(self) -> None:
        self.payloads = []

    def send(self, payload) -> None:
        self.payloads.append(payload)


def build_message_event(message_id: str, text: str, *, sender_id: str = "ou_test_user") -> SimpleNamespace:
    return SimpleNamespace(
        schema="2.0",
        header=SimpleNamespace(event_type="im.message.receive_v1", tenant_key="tenant-test"),
        event=SimpleNamespace(
            sender=SimpleNamespace(
                sender_type="user",
                tenant_key="tenant-test",
                sender_id=SimpleNamespace(user_id=sender_id, open_id=sender_id, union_id=None),
            ),
            message=SimpleNamespace(
                message_id=message_id,
                chat_id="chat-test",
                chat_type="p2p",
                message_type="text",
                content=json.dumps({"text": text}, ensure_ascii=False),
                create_time="0",
            ),
        ),
    )


def reset_database() -> None:
    with SessionLocal() as session:
        session.query(Message).delete()
        session.query(AlertEvent).delete()
        session.query(Contact).delete()
        session.query(PendingAdminChange).delete()
        session.query(User).delete()

        template = get_or_create_email_template(session)
        template.subject = DEFAULT_TEMPLATE_SUBJECT
        template.body = DEFAULT_TEMPLATE_BODY
        template.version = 1
        template.is_active = True
        session.add(template)
        session.commit()

        update_settings(
            session,
            default_llm_provider="openai",
            default_llm_model="gpt-4.1-mini",
            alert_default_hours=72,
            chat_context_messages=10,
            chat_prompt_version="chat_v2",
            command_repair_prompt_version="command_repair_v1",
            command_repair_enabled=True,
            admin_feishu_user_id="",
        )


def build_test_client() -> TestClient:
    app_main.start_feishu_long_connection = lambda: None
    return TestClient(app_main.app)
