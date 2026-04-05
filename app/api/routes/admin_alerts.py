from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.alerts import AlertingService
from app.api.deps.admin import require_admin_token
from app.core.config import settings
from app.db.models.app_settings import AppSettings
from app.db.models.contact import Contact
from app.db.models.email_template import EmailTemplate
from app.db.models.user import User
from app.db.session import get_db_session
from app.mail import TemplateValidationError, validate_alert_template

router = APIRouter(prefix="/admin", tags=["admin"])

ALLOWED_PROVIDERS = {"openai", "anthropic", "gemini"}
ALERT_TEMPLATE_KEY = "alert_default"


class TestAlertRequest(BaseModel):
    recipients: list[str] = Field(min_length=1)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)


class SettingsResponse(BaseModel):
    default_llm_provider: str
    default_llm_model: str
    alert_default_hours: int
    chat_context_messages: int
    admin_feishu_user_id: str | None


class SettingsPatchRequest(BaseModel):
    default_llm_provider: str | None = None
    default_llm_model: str | None = None
    alert_default_hours: int | None = Field(default=None, ge=1)
    chat_context_messages: int | None = Field(default=None, ge=1, le=100)
    admin_feishu_user_id: str | None = None


class ContactItem(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320)
    relation: str | None = Field(default=None, max_length=64)
    priority: int = Field(default=1, ge=1, le=100)
    enabled: bool = True


class ContactsResponse(BaseModel):
    managed_feishu_user_id: str
    contacts: list[ContactItem]


class ContactsPutRequest(BaseModel):
    contacts: list[ContactItem]


class EmailTemplateResponse(BaseModel):
    template_key: str
    subject: str
    body: str
    version: int
    is_active: bool


class EmailTemplatePutRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)


@router.post("/test-alert", dependencies=[Depends(require_admin_token)])
def test_alert(request: TestAlertRequest) -> dict[str, int | str]:
    service = AlertingService()
    delivered = service.send_test_alert(
        recipients=request.recipients,
        subject=request.subject,
        body=request.body,
    )
    return {"status": "sent", "delivered": delivered}


@router.get("/settings", dependencies=[Depends(require_admin_token)], response_model=SettingsResponse)
def get_settings(session: Session = Depends(get_db_session)) -> SettingsResponse:
    app_settings = _get_or_create_app_settings(session)
    return _serialize_settings(app_settings)


@router.patch("/settings", dependencies=[Depends(require_admin_token)], response_model=SettingsResponse)
def patch_settings(request: SettingsPatchRequest, session: Session = Depends(get_db_session)) -> SettingsResponse:
    app_settings = _get_or_create_app_settings(session)

    if request.default_llm_provider is not None:
        provider = request.default_llm_provider.strip().lower()
        if provider not in ALLOWED_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"default_llm_provider must be one of: {', '.join(sorted(ALLOWED_PROVIDERS))}.",
            )
        app_settings.default_llm_provider = provider

    if request.default_llm_model is not None:
        model = request.default_llm_model.strip()
        if not model:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="default_llm_model cannot be empty.")
        app_settings.default_llm_model = model

    if request.alert_default_hours is not None:
        app_settings.alert_default_hours = request.alert_default_hours

    if request.chat_context_messages is not None:
        app_settings.chat_context_messages = request.chat_context_messages

    if request.admin_feishu_user_id is not None:
        app_settings.admin_feishu_user_id = request.admin_feishu_user_id.strip() or None

    session.add(app_settings)
    session.commit()
    session.refresh(app_settings)
    return _serialize_settings(app_settings)


@router.get("/contacts", dependencies=[Depends(require_admin_token)], response_model=ContactsResponse)
def get_contacts(session: Session = Depends(get_db_session)) -> ContactsResponse:
    user = _resolve_managed_user(session, create_if_missing=False)
    contacts = (
        session.query(Contact)
        .filter(Contact.user_id == user.id)
        .order_by(Contact.priority.asc(), Contact.created_at.asc())
        .all()
    )
    return ContactsResponse(
        managed_feishu_user_id=user.feishu_user_id,
        contacts=[_serialize_contact(contact) for contact in contacts],
    )


@router.put("/contacts", dependencies=[Depends(require_admin_token)], response_model=ContactsResponse)
def put_contacts(request: ContactsPutRequest, session: Session = Depends(get_db_session)) -> ContactsResponse:
    user = _resolve_managed_user(session, create_if_missing=True)
    normalized_contacts = _normalize_contacts(request.contacts)

    session.query(Contact).filter(Contact.user_id == user.id).delete()
    for item in normalized_contacts:
        session.add(
            Contact(
                user_id=user.id,
                name=item.name,
                email=item.email,
                relation=item.relation,
                priority=item.priority,
                enabled=item.enabled,
            )
        )

    session.commit()

    contacts = (
        session.query(Contact)
        .filter(Contact.user_id == user.id)
        .order_by(Contact.priority.asc(), Contact.created_at.asc())
        .all()
    )
    return ContactsResponse(
        managed_feishu_user_id=user.feishu_user_id,
        contacts=[_serialize_contact(contact) for contact in contacts],
    )


@router.get("/email-template", dependencies=[Depends(require_admin_token)], response_model=EmailTemplateResponse)
def get_email_template(session: Session = Depends(get_db_session)) -> EmailTemplateResponse:
    template = _get_or_create_email_template(session)
    return _serialize_email_template(template)


@router.put("/email-template", dependencies=[Depends(require_admin_token)], response_model=EmailTemplateResponse)
def put_email_template(request: EmailTemplatePutRequest, session: Session = Depends(get_db_session)) -> EmailTemplateResponse:
    try:
        validate_alert_template(request.subject, request.body)
    except TemplateValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    template = _get_or_create_email_template(session)
    template.subject = request.subject
    template.body = request.body
    template.version += 1
    template.is_active = True
    session.add(template)
    session.commit()
    session.refresh(template)
    return _serialize_email_template(template)


def _get_or_create_app_settings(session: Session) -> AppSettings:
    app_settings = session.get(AppSettings, 1)
    if app_settings is not None:
        return app_settings

    app_settings = AppSettings(
        id=1,
        default_llm_provider=settings.default_llm_provider,
        default_llm_model=settings.default_llm_model,
        alert_default_hours=settings.alert_default_hours,
        chat_context_messages=settings.chat_context_messages,
        admin_feishu_user_id=settings.admin_feishu_user_id or None,
    )
    session.add(app_settings)
    session.commit()
    session.refresh(app_settings)
    return app_settings


def _serialize_settings(app_settings: AppSettings) -> SettingsResponse:
    return SettingsResponse(
        default_llm_provider=app_settings.default_llm_provider,
        default_llm_model=app_settings.default_llm_model,
        alert_default_hours=app_settings.alert_default_hours,
        chat_context_messages=app_settings.chat_context_messages,
        admin_feishu_user_id=app_settings.admin_feishu_user_id,
    )


def _resolve_managed_user(session: Session, create_if_missing: bool) -> User:
    app_settings = _get_or_create_app_settings(session)
    admin_feishu_user_id = (app_settings.admin_feishu_user_id or "").strip()

    if admin_feishu_user_id:
        user = session.query(User).filter(User.feishu_user_id == admin_feishu_user_id).one_or_none()
        if user is not None:
            return user
        if create_if_missing:
            user = User(
                feishu_user_id=admin_feishu_user_id,
                timezone=settings.app_timezone,
                status="ACTIVE",
                last_seen_at=datetime.now(timezone.utc),
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Managed user does not exist yet. Send a Feishu message first or use PUT /admin/contacts to create it.",
        )

    user = session.query(User).order_by(User.last_seen_at.desc(), User.created_at.desc()).first()
    if user is not None:
        return user

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Cannot determine the managed user. Set admin_feishu_user_id first or send a Feishu message.",
    )


def _normalize_contacts(items: list[ContactItem]) -> list[ContactItem]:
    normalized_contacts: list[ContactItem] = []
    seen_emails: set[str] = set()
    for item in items:
        normalized_email = item.email.strip().lower()
        if "@" not in normalized_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid email: {item.email}")
        if normalized_email in seen_emails:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate contact email: {normalized_email}",
            )
        seen_emails.add(normalized_email)
        normalized_contacts.append(
            ContactItem(
                name=item.name.strip(),
                email=normalized_email,
                relation=item.relation.strip() if item.relation else None,
                priority=item.priority,
                enabled=item.enabled,
            )
        )
    return normalized_contacts


def _serialize_contact(contact: Contact) -> ContactItem:
    return ContactItem(
        name=contact.name,
        email=contact.email,
        relation=contact.relation,
        priority=contact.priority,
        enabled=contact.enabled,
    )


def _get_or_create_email_template(session: Session) -> EmailTemplate:
    template = (
        session.query(EmailTemplate)
        .filter(EmailTemplate.template_key == ALERT_TEMPLATE_KEY)
        .order_by(EmailTemplate.updated_at.desc())
        .first()
    )
    if template is not None:
        return template

    template = EmailTemplate(
        template_key=ALERT_TEMPLATE_KEY,
        subject="长时间未联系提醒：{user_name}",
        body=(
            "你好，{contact_name}。\n\n"
            "系统检测到 {user_name} 已连续 {inactive_hours} 小时未通过飞书与机器人互动。\n"
            "最后一次记录时间：{last_seen_at}。\n\n"
            "这是一条自动提醒消息，仅用于提示你主动确认对方近况，并不代表系统已确认异常。"
        ),
        version=1,
        is_active=True,
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


def _serialize_email_template(template: EmailTemplate) -> EmailTemplateResponse:
    return EmailTemplateResponse(
        template_key=template.template_key,
        subject=template.subject,
        body=template.body,
        version=template.version,
        is_active=template.is_active,
    )
