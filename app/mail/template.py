from dataclasses import dataclass
from datetime import datetime
from string import Formatter


ALLOWED_TEMPLATE_FIELDS = {"user_name", "last_seen_at", "inactive_hours", "contact_name"}


class TemplateValidationError(ValueError):
    pass


@dataclass(frozen=True)
class AlertTemplateContent:
    subject: str
    body: str


@dataclass(frozen=True)
class AlertTemplateVariables:
    user_name: str
    last_seen_at: str
    inactive_hours: int
    contact_name: str


def validate_alert_template(subject: str, body: str) -> None:
    _validate_string_template(subject)
    _validate_string_template(body)


def render_alert_template(template: AlertTemplateContent, variables: AlertTemplateVariables) -> AlertTemplateContent:
    validate_alert_template(template.subject, template.body)
    values = {
        "user_name": variables.user_name,
        "last_seen_at": variables.last_seen_at,
        "inactive_hours": variables.inactive_hours,
        "contact_name": variables.contact_name,
    }
    return AlertTemplateContent(
        subject=template.subject.format_map(values),
        body=template.body.format_map(values),
    )


def format_last_seen_at(value: datetime) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _validate_string_template(template: str) -> None:
    formatter = Formatter()
    for _, field_name, _, _ in formatter.parse(template):
        if field_name is None:
            continue
        if field_name not in ALLOWED_TEMPLATE_FIELDS:
            allowed = ", ".join(sorted(ALLOWED_TEMPLATE_FIELDS))
            raise TemplateValidationError(f"Unsupported template variable: {field_name}. Allowed: {allowed}")
