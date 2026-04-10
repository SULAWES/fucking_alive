from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.alerts import AlertingService
from app.api.deps.admin import require_admin_token
from app.db.session import get_db_session
from app.mail import TemplateValidationError
from app.services.admin_config_service import (
    ALLOWED_PROVIDERS,
    AdminContactData,
    get_or_create_app_settings,
    get_or_create_email_template,
    list_contacts,
    normalize_contacts,
    replace_contacts,
    resolve_managed_user,
    serialize_contact,
    serialize_email_template,
    serialize_settings,
    update_email_template,
    update_settings,
)

router = APIRouter(prefix="/admin", tags=["admin"])


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
    app_settings = get_or_create_app_settings(session)
    return _serialize_settings(app_settings)


@router.patch("/settings", dependencies=[Depends(require_admin_token)], response_model=SettingsResponse)
def patch_settings(request: SettingsPatchRequest, session: Session = Depends(get_db_session)) -> SettingsResponse:
    try:
        app_settings = update_settings(
            session,
            default_llm_provider=request.default_llm_provider,
            default_llm_model=request.default_llm_model,
            alert_default_hours=request.alert_default_hours,
            chat_context_messages=request.chat_context_messages,
            admin_feishu_user_id=request.admin_feishu_user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize_settings(app_settings)


@router.get("/contacts", dependencies=[Depends(require_admin_token)], response_model=ContactsResponse)
def get_contacts(session: Session = Depends(get_db_session)) -> ContactsResponse:
    try:
        user = resolve_managed_user(session, create_if_missing=False)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    contacts = list_contacts(session, user)
    return ContactsResponse(
        managed_feishu_user_id=user.feishu_user_id,
        contacts=[_serialize_contact(contact) for contact in contacts],
    )


@router.put("/contacts", dependencies=[Depends(require_admin_token)], response_model=ContactsResponse)
def put_contacts(request: ContactsPutRequest, session: Session = Depends(get_db_session)) -> ContactsResponse:
    try:
        user = resolve_managed_user(session, create_if_missing=True)
        contacts = replace_contacts(
            session,
            user,
            [
                AdminContactData(
                    name=item.name,
                    email=item.email,
                    relation=item.relation,
                    priority=item.priority,
                    enabled=item.enabled,
                )
                for item in request.contacts
            ],
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ContactsResponse(
        managed_feishu_user_id=user.feishu_user_id,
        contacts=[_serialize_contact(contact) for contact in contacts],
    )


@router.get("/email-template", dependencies=[Depends(require_admin_token)], response_model=EmailTemplateResponse)
def get_email_template(session: Session = Depends(get_db_session)) -> EmailTemplateResponse:
    template = get_or_create_email_template(session)
    return _serialize_email_template(template)


@router.put("/email-template", dependencies=[Depends(require_admin_token)], response_model=EmailTemplateResponse)
def put_email_template(request: EmailTemplatePutRequest, session: Session = Depends(get_db_session)) -> EmailTemplateResponse:
    try:
        template = update_email_template(session, subject=request.subject, body=request.body)
    except TemplateValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize_email_template(template)


def _serialize_settings(app_settings) -> SettingsResponse:
    data = serialize_settings(app_settings)
    return SettingsResponse(
        default_llm_provider=data.default_llm_provider,
        default_llm_model=data.default_llm_model,
        alert_default_hours=data.alert_default_hours,
        chat_context_messages=data.chat_context_messages,
        admin_feishu_user_id=data.admin_feishu_user_id,
    )


def _serialize_contact(contact) -> ContactItem:
    data = serialize_contact(contact)
    return ContactItem(
        name=data.name,
        email=data.email,
        relation=data.relation,
        priority=data.priority,
        enabled=data.enabled,
    )


def _serialize_email_template(template) -> EmailTemplateResponse:
    data = serialize_email_template(template)
    return EmailTemplateResponse(
        template_key=data.template_key,
        subject=data.subject,
        body=data.body,
        version=data.version,
        is_active=data.is_active,
    )
