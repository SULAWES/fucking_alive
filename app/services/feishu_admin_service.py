import shlex
from datetime import datetime, timedelta, timezone

from app.db.models.pending_admin_change import PendingAdminChange
from app.services.admin_config_service import (
    AdminContactData,
    get_or_create_app_settings,
    get_or_create_email_template,
    is_admin_user,
    list_contacts,
    normalize_contacts,
    replace_contacts,
    resolve_managed_user,
    update_email_template,
)

PENDING_CHANGE_TTL_MINUTES = 30
NO_PERMISSION_TEXT = "当前命令仅管理员可用。"


class FeishuAdminService:
    def build_help_text(self, session, sender_feishu_user_id: str) -> str:
        base_lines = [
            "可用命令：",
            "/help 查看帮助",
            "/alive 手动报平安",
        ]
        if is_admin_user(session, sender_feishu_user_id):
            base_lines.extend(
                [
                    "",
                    "管理员命令：",
                    "/contacts list",
                    "/contacts add <name> <email> [relation]",
                    "/contacts update <email> <name> [relation] [enabled]",
                    "/contacts remove <email>",
                    "/template show",
                    "/template subject set <text>",
                    "/template body set <text>",
                    "/config confirm",
                    "/config cancel",
                ]
            )
        else:
            base_lines.extend(
                [
                    "",
                    "当前阶段已接入 OpenAI 兼容格式对话。",
                    "Anthropic / Gemini 适配器仍为占位。",
                ]
            )
        return "\n".join(base_lines)

    def handle_command(self, session, sender_feishu_user_id: str, text: str) -> str | None:
        normalized = text.strip()
        if not normalized.startswith("/"):
            return None
        if normalized in {"/alive", "/help"}:
            return None

        self._cleanup_expired_changes(session, sender_feishu_user_id)

        if normalized == "/config confirm":
            return self._confirm_pending_change(session, sender_feishu_user_id)
        if normalized == "/config cancel":
            return self._cancel_pending_change(session, sender_feishu_user_id)
        if normalized == "/contacts list":
            return self._list_contacts(session, sender_feishu_user_id)
        if normalized.startswith("/contacts add "):
            return self._add_contact(session, sender_feishu_user_id, normalized)
        if normalized.startswith("/contacts update "):
            return self._update_contact(session, sender_feishu_user_id, normalized)
        if normalized.startswith("/contacts remove "):
            return self._remove_contact(session, sender_feishu_user_id, normalized)
        if normalized == "/template show":
            return self._show_template(session, sender_feishu_user_id)
        if normalized.startswith("/template subject set "):
            return self._set_template_subject(session, sender_feishu_user_id, normalized)
        if normalized.startswith("/template body set "):
            return self._set_template_body(session, sender_feishu_user_id, normalized)
        return None

    def _list_contacts(self, session, sender_feishu_user_id: str) -> str:
        if not is_admin_user(session, sender_feishu_user_id):
            return NO_PERMISSION_TEXT
        try:
            user = resolve_managed_user(session, create_if_missing=False)
        except LookupError as exc:
            return str(exc)

        contacts = list_contacts(session, user)
        if not contacts:
            return "当前没有联系人。"

        lines = ["当前联系人："]
        for contact in contacts:
            relation = f" relation={contact.relation}" if contact.relation else ""
            enabled = "enabled" if contact.enabled else "disabled"
            lines.append(f"- {contact.name} <{contact.email}> priority={contact.priority} {enabled}{relation}")
        return "\n".join(lines)

    def _add_contact(self, session, sender_feishu_user_id: str, text: str) -> str:
        if not is_admin_user(session, sender_feishu_user_id):
            return NO_PERMISSION_TEXT
        try:
            tokens = shlex.split(text)
        except ValueError as exc:
            return f"命令解析失败：{exc}"
        if len(tokens) < 4:
            return "用法：/contacts add <name> <email> [relation]"

        try:
            user = resolve_managed_user(session, create_if_missing=True)
            contacts = self._get_pending_contacts_or_current(session, sender_feishu_user_id, user)
            next_priority = max((contact.priority for contact in contacts), default=0) + 1
            contacts.append(
                AdminContactData(
                    name=tokens[2],
                    email=tokens[3],
                    relation=tokens[4] if len(tokens) > 4 else None,
                    priority=next_priority,
                    enabled=True,
                )
            )
            payload_contacts = normalize_contacts(contacts)
        except (LookupError, ValueError) as exc:
            return str(exc)

        return self._create_pending_change(
            session,
            sender_feishu_user_id,
            "contacts",
            {"contacts": [_serialize_contact_payload(contact) for contact in payload_contacts]},
        )

    def _update_contact(self, session, sender_feishu_user_id: str, text: str) -> str:
        if not is_admin_user(session, sender_feishu_user_id):
            return NO_PERMISSION_TEXT
        try:
            tokens = shlex.split(text)
        except ValueError as exc:
            return f"命令解析失败：{exc}"
        if len(tokens) < 4:
            return "用法：/contacts update <email> <name> [relation] [enabled]"

        try:
            user = resolve_managed_user(session, create_if_missing=False)
        except LookupError as exc:
            return str(exc)

        target_email = tokens[2].strip().lower()
        contacts = self._get_pending_contacts_or_current(session, sender_feishu_user_id, user)
        updated_contacts: list[AdminContactData] = []
        found = False
        for contact in contacts:
            if contact.email != target_email:
                updated_contacts.append(contact)
                continue

            found = True
            relation = contact.relation
            enabled = contact.enabled
            extra_tokens = tokens[4:]
            if len(extra_tokens) == 1:
                parsed_enabled = _parse_enabled_value(extra_tokens[0])
                if parsed_enabled is None:
                    relation = extra_tokens[0]
                else:
                    enabled = parsed_enabled
            elif len(extra_tokens) >= 2:
                relation = extra_tokens[0]
                parsed_enabled = _parse_enabled_value(extra_tokens[1])
                if parsed_enabled is None:
                    return "enabled 参数必须为 true/false、enabled/disabled、yes/no 或 1/0。"
                enabled = parsed_enabled

            updated_contacts.append(
                AdminContactData(
                    name=tokens[3],
                    email=contact.email,
                    relation=relation,
                    priority=contact.priority,
                    enabled=enabled,
                )
            )

        if not found:
            return f"联系人不存在：{target_email}"

        try:
            payload_contacts = normalize_contacts(updated_contacts)
        except ValueError as exc:
            return str(exc)

        return self._create_pending_change(
            session,
            sender_feishu_user_id,
            "contacts",
            {"contacts": [_serialize_contact_payload(contact) for contact in payload_contacts]},
        )

    def _remove_contact(self, session, sender_feishu_user_id: str, text: str) -> str:
        if not is_admin_user(session, sender_feishu_user_id):
            return NO_PERMISSION_TEXT
        try:
            tokens = shlex.split(text)
        except ValueError as exc:
            return f"命令解析失败：{exc}"
        if len(tokens) != 3:
            return "用法：/contacts remove <email>"

        try:
            user = resolve_managed_user(session, create_if_missing=False)
        except LookupError as exc:
            return str(exc)

        target_email = tokens[2].strip().lower()
        contacts = self._get_pending_contacts_or_current(session, sender_feishu_user_id, user)
        filtered_contacts = [contact for contact in contacts if contact.email != target_email]
        if len(filtered_contacts) == len(contacts):
            return f"联系人不存在：{target_email}"

        return self._create_pending_change(
            session,
            sender_feishu_user_id,
            "contacts",
            {"contacts": [_serialize_contact_payload(contact) for contact in filtered_contacts]},
        )

    def _show_template(self, session, sender_feishu_user_id: str) -> str:
        if not is_admin_user(session, sender_feishu_user_id):
            return NO_PERMISSION_TEXT
        template = get_or_create_email_template(session)
        return f"当前模板：\nsubject: {template.subject}\nbody:\n{template.body}"

    def _set_template_subject(self, session, sender_feishu_user_id: str, text: str) -> str:
        if not is_admin_user(session, sender_feishu_user_id):
            return NO_PERMISSION_TEXT
        subject = text.removeprefix("/template subject set ").strip()
        if not subject:
            return "用法：/template subject set <text>"
        template = self._get_pending_template_or_current(session, sender_feishu_user_id)
        return self._create_pending_change(
            session,
            sender_feishu_user_id,
            "email_template",
            {"subject": subject, "body": template["body"]},
        )

    def _set_template_body(self, session, sender_feishu_user_id: str, text: str) -> str:
        if not is_admin_user(session, sender_feishu_user_id):
            return NO_PERMISSION_TEXT
        body = text.removeprefix("/template body set ").strip()
        if not body:
            return "用法：/template body set <text>"
        template = self._get_pending_template_or_current(session, sender_feishu_user_id)
        return self._create_pending_change(
            session,
            sender_feishu_user_id,
            "email_template",
            {"subject": template["subject"], "body": body},
        )

    def _confirm_pending_change(self, session, sender_feishu_user_id: str) -> str:
        if not is_admin_user(session, sender_feishu_user_id):
            return NO_PERMISSION_TEXT
        pending = self._get_active_pending_change(session, sender_feishu_user_id)
        if pending is None:
            return "当前没有待确认的变更。"

        if pending.change_type == "contacts":
            try:
                user = resolve_managed_user(session, create_if_missing=True)
                contacts = [
                    AdminContactData(
                        name=item["name"],
                        email=item["email"],
                        relation=item.get("relation"),
                        priority=item.get("priority", 1),
                        enabled=item.get("enabled", True),
                    )
                    for item in pending.payload.get("contacts", [])
                ]
                replace_contacts(session, user, contacts)
            except (LookupError, ValueError) as exc:
                return str(exc)
            message = self._format_contacts_preview(contacts, title="联系人变更已生效：")
        elif pending.change_type == "email_template":
            try:
                template = update_email_template(
                    session,
                    subject=str(pending.payload.get("subject", "")),
                    body=str(pending.payload.get("body", "")),
                )
            except Exception as exc:
                return str(exc)
            message = f"模板变更已生效：\nsubject: {template.subject}\nbody:\n{template.body}"
        else:
            return f"未知待确认变更类型：{pending.change_type}"

        session.delete(pending)
        session.commit()
        return message

    def _cancel_pending_change(self, session, sender_feishu_user_id: str) -> str:
        if not is_admin_user(session, sender_feishu_user_id):
            return NO_PERMISSION_TEXT
        pending = self._get_active_pending_change(session, sender_feishu_user_id)
        if pending is None:
            return "当前没有待确认的变更。"
        session.delete(pending)
        session.commit()
        return "已取消当前待确认变更。"

    def _create_pending_change(self, session, sender_feishu_user_id: str, change_type: str, payload: dict) -> str:
        now = datetime.now(timezone.utc)
        self._cleanup_expired_changes(session, sender_feishu_user_id)
        existing = (
            session.query(PendingAdminChange)
            .filter(PendingAdminChange.admin_feishu_user_id == sender_feishu_user_id)
            .all()
        )
        for record in existing:
            session.delete(record)

        pending = PendingAdminChange(
            admin_feishu_user_id=sender_feishu_user_id,
            change_type=change_type,
            payload=payload,
            expires_at=now + timedelta(minutes=PENDING_CHANGE_TTL_MINUTES),
        )
        session.add(pending)
        session.commit()
        session.refresh(pending)

        if change_type == "contacts":
            contacts = [
                AdminContactData(
                    name=item["name"],
                    email=item["email"],
                    relation=item.get("relation"),
                    priority=item.get("priority", 1),
                    enabled=item.get("enabled", True),
                )
                for item in payload.get("contacts", [])
            ]
            preview = self._format_contacts_preview(contacts, title="联系人变更待确认：")
        else:
            preview = f"模板变更待确认：\nsubject: {payload.get('subject', '')}\nbody:\n{payload.get('body', '')}"

        return (
            f"{preview}\n\n"
            f"请在 {PENDING_CHANGE_TTL_MINUTES} 分钟内发送 /config confirm 确认，"
            "或发送 /config cancel 取消。"
        )

    def _get_active_pending_change(self, session, sender_feishu_user_id: str) -> PendingAdminChange | None:
        self._cleanup_expired_changes(session, sender_feishu_user_id)
        return (
            session.query(PendingAdminChange)
            .filter(PendingAdminChange.admin_feishu_user_id == sender_feishu_user_id)
            .order_by(PendingAdminChange.created_at.desc())
            .first()
        )

    def _cleanup_expired_changes(self, session, sender_feishu_user_id: str) -> None:
        deleted = (
            session.query(PendingAdminChange)
            .filter(
                PendingAdminChange.admin_feishu_user_id == sender_feishu_user_id,
                PendingAdminChange.expires_at <= datetime.now(timezone.utc),
            )
            .delete()
        )
        if deleted:
            session.commit()

    def _format_contacts_preview(self, contacts: list[AdminContactData], *, title: str) -> str:
        if not contacts:
            return f"{title}\n- 当前结果为空"

        lines = [title]
        for contact in sorted(contacts, key=lambda item: (item.priority, item.email)):
            relation = f" relation={contact.relation}" if contact.relation else ""
            enabled = "enabled" if contact.enabled else "disabled"
            lines.append(f"- {contact.name} <{contact.email}> priority={contact.priority} {enabled}{relation}")
        return "\n".join(lines)

    def _get_pending_contacts_or_current(self, session, sender_feishu_user_id: str, user) -> list[AdminContactData]:
        pending = self._get_active_pending_change(session, sender_feishu_user_id)
        if pending is not None and pending.change_type == "contacts":
            return [
                AdminContactData(
                    name=item["name"],
                    email=item["email"],
                    relation=item.get("relation"),
                    priority=item.get("priority", 1),
                    enabled=item.get("enabled", True),
                )
                for item in pending.payload.get("contacts", [])
            ]
        return [
            AdminContactData(
                name=contact.name,
                email=contact.email,
                relation=contact.relation,
                priority=contact.priority,
                enabled=contact.enabled,
            )
            for contact in list_contacts(session, user)
        ]

    def _get_pending_template_or_current(self, session, sender_feishu_user_id: str) -> dict[str, str]:
        pending = self._get_active_pending_change(session, sender_feishu_user_id)
        if pending is not None and pending.change_type == "email_template":
            return {
                "subject": str(pending.payload.get("subject", "")),
                "body": str(pending.payload.get("body", "")),
            }

        template = get_or_create_email_template(session)
        return {"subject": template.subject, "body": template.body}


def _parse_enabled_value(value: str) -> bool | None:
    normalized = value.strip().lower()
    mapping = {
        "true": True,
        "false": False,
        "enabled": True,
        "disabled": False,
        "yes": True,
        "no": False,
        "1": True,
        "0": False,
    }
    return mapping.get(normalized)


def _serialize_contact_payload(contact: AdminContactData) -> dict:
    return {
        "name": contact.name,
        "email": contact.email,
        "relation": contact.relation,
        "priority": contact.priority,
        "enabled": contact.enabled,
    }
