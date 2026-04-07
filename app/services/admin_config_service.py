from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings
from app.db.models.app_settings import AppSettings
from app.db.models.contact import Contact
from app.db.models.email_template import EmailTemplate
from app.db.models.user import User
from app.mail import TemplateValidationError, validate_alert_template

ALLOWED_PROVIDERS = {"openai", "anthropic", "gemini"}
ALERT_TEMPLATE_KEY = "alert_default"
DEFAULT_TEMPLATE_SUBJECT = "长时间未联系提醒：{user_name}"
DEFAULT_TEMPLATE_BODY = (
    "你好，{contact_name}。\n\n"
    "系统检测到 {user_name} 已连续 {inactive_hours} 小时未通过飞书与机器人互动。\n"
    "最后一次记录时间：{last_seen_at}。\n\n"
    "这是一条自动提醒消息，仅用于提示你主动确认对方近况，并不代表系统已确认异常。"
)


@dataclass(frozen=True)
class AdminSettingsData:
    default_llm_provider: str
    default_llm_model: str
    alert_default_hours: int
    chat_context_messages: int
    admin_feishu_user_id: str | None


@dataclass(frozen=True)
class AdminContactData:
    name: str
    email: str
    relation: str | None = None
    priority: int = 1
    enabled: bool = True


@dataclass(frozen=True)
class AdminEmailTemplateData:
    template_key: str
    subject: str
    body: str
    version: int
    is_active: bool


def get_or_create_app_settings(session) -> AppSettings:
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


def serialize_settings(app_settings: AppSettings) -> AdminSettingsData:
    return AdminSettingsData(
        default_llm_provider=app_settings.default_llm_provider,
        default_llm_model=app_settings.default_llm_model,
        alert_default_hours=app_settings.alert_default_hours,
        chat_context_messages=app_settings.chat_context_messages,
        admin_feishu_user_id=app_settings.admin_feishu_user_id,
    )


def update_settings(
    session,
    *,
    default_llm_provider: str | None = None,
    default_llm_model: str | None = None,
    alert_default_hours: int | None = None,
    chat_context_messages: int | None = None,
    admin_feishu_user_id: str | None = None,
) -> AppSettings:
    app_settings = get_or_create_app_settings(session)

    if default_llm_provider is not None:
        provider = default_llm_provider.strip().lower()
        if provider not in ALLOWED_PROVIDERS:
            raise ValueError(f"default_llm_provider must be one of: {', '.join(sorted(ALLOWED_PROVIDERS))}.")
        app_settings.default_llm_provider = provider

    if default_llm_model is not None:
        model = default_llm_model.strip()
        if not model:
            raise ValueError("default_llm_model cannot be empty.")
        app_settings.default_llm_model = model

    if alert_default_hours is not None:
        app_settings.alert_default_hours = alert_default_hours

    if chat_context_messages is not None:
        app_settings.chat_context_messages = chat_context_messages

    if admin_feishu_user_id is not None:
        app_settings.admin_feishu_user_id = admin_feishu_user_id.strip() or None

    session.add(app_settings)
    session.commit()
    session.refresh(app_settings)
    return app_settings


def is_admin_user(session, feishu_user_id: str) -> bool:
    admin_feishu_user_id = (get_or_create_app_settings(session).admin_feishu_user_id or "").strip()
    return bool(admin_feishu_user_id and admin_feishu_user_id == feishu_user_id)


def resolve_managed_user(session, *, create_if_missing: bool) -> User:
    app_settings = get_or_create_app_settings(session)
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
        raise LookupError("Managed user does not exist yet.")

    user = session.query(User).order_by(User.last_seen_at.desc(), User.created_at.desc()).first()
    if user is not None:
        return user

    raise LookupError("Cannot determine the managed user.")


def list_contacts(session, user: User) -> list[Contact]:
    return (
        session.query(Contact)
        .filter(Contact.user_id == user.id)
        .order_by(Contact.priority.asc(), Contact.created_at.asc())
        .all()
    )


def serialize_contact(contact: Contact) -> AdminContactData:
    return AdminContactData(
        name=contact.name,
        email=contact.email,
        relation=contact.relation,
        priority=contact.priority,
        enabled=contact.enabled,
    )


def normalize_contacts(items: list[AdminContactData]) -> list[AdminContactData]:
    normalized_contacts: list[AdminContactData] = []
    seen_emails: set[str] = set()
    for item in items:
        normalized_email = item.email.strip().lower()
        if "@" not in normalized_email:
            raise ValueError(f"Invalid email: {item.email}")
        if normalized_email in seen_emails:
            raise ValueError(f"Duplicate contact email: {normalized_email}")
        seen_emails.add(normalized_email)
        normalized_contacts.append(
            AdminContactData(
                name=item.name.strip(),
                email=normalized_email,
                relation=item.relation.strip() if item.relation else None,
                priority=item.priority,
                enabled=item.enabled,
            )
        )
    return normalized_contacts


def replace_contacts(session, user: User, items: list[AdminContactData]) -> list[Contact]:
    normalized_contacts = normalize_contacts(items)
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
    return list_contacts(session, user)


def get_or_create_email_template(session) -> EmailTemplate:
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
        subject=DEFAULT_TEMPLATE_SUBJECT,
        body=DEFAULT_TEMPLATE_BODY,
        version=1,
        is_active=True,
    )
    session.add(template)
    session.commit()
    session.refresh(template)
    return template


def serialize_email_template(template: EmailTemplate) -> AdminEmailTemplateData:
    return AdminEmailTemplateData(
        template_key=template.template_key,
        subject=template.subject,
        body=template.body,
        version=template.version,
        is_active=template.is_active,
    )


def update_email_template(session, *, subject: str, body: str) -> EmailTemplate:
    validate_alert_template(subject, body)
    template = get_or_create_email_template(session)
    template.subject = subject
    template.body = body
    template.version += 1
    template.is_active = True
    session.add(template)
    session.commit()
    session.refresh(template)
    return template
