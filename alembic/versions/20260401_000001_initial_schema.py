"""initial schema

Revision ID: 20260401_000001
Revises: 
Create Date: 2026-04-01 20:40:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260401_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feishu_user_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("feishu_user_id", name=op.f("uq_users_feishu_user_id")),
    )

    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("default_llm_provider", sa.String(length=32), nullable=False),
        sa.Column("default_llm_model", sa.String(length=128), nullable=False),
        sa.Column("alert_default_hours", sa.Integer(), nullable=False),
        sa.Column("chat_context_messages", sa.Integer(), nullable=False),
        sa.Column("admin_feishu_user_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_settings")),
    )

    op.create_table(
        "email_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_key", sa.String(length=128), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_templates")),
        sa.UniqueConstraint("template_key", name=op.f("uq_email_templates_template_key")),
    )

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("relation", sa.String(length=64), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_contacts_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
        sa.UniqueConstraint("user_id", "email", name="uq_contacts_user_id_email"),
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("feishu_message_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_messages_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(
        "uq_messages_feishu_message_id",
        "messages",
        ["feishu_message_id"],
        unique=True,
        postgresql_where=sa.text("feishu_message_id IS NOT NULL"),
    )
    op.create_index(op.f("ix_messages_user_id"), "messages", ["user_id"], unique=False)

    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_alert_events_contact_id_contacts"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_alert_events_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_events")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_alert_events_dedupe_key")),
    )
    op.create_index(op.f("ix_alert_events_user_id"), "alert_events", ["user_id"], unique=False)

    op.create_table(
        "pending_admin_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_feishu_user_id", sa.String(length=128), nullable=False),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pending_admin_changes")),
    )
    op.create_index(
        op.f("ix_pending_admin_changes_admin_feishu_user_id"),
        "pending_admin_changes",
        ["admin_feishu_user_id"],
        unique=False,
    )

    op.execute(
        sa.text(
            """
            INSERT INTO app_settings (
                id, default_llm_provider, default_llm_model, alert_default_hours,
                chat_context_messages, admin_feishu_user_id
            )
            VALUES (
                1, 'openai', 'gpt-4.1-mini', 72, 10, NULL
            )
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO email_templates (
                id, template_key, subject, body, version, is_active
            )
            VALUES (
                '11111111-1111-1111-1111-111111111111',
                'alert_default',
                '长时间未联系提醒：{user_name}',
                '你好，{contact_name}。\n\n系统检测到 {user_name} 已连续 {inactive_hours} 小时未通过飞书与机器人互动。\n最后一次记录时间：{last_seen_at}。\n\n这是一条自动提醒消息，仅用于提示你主动确认对方近况，并不代表系统已确认异常。',
                1,
                TRUE
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pending_admin_changes_admin_feishu_user_id"), table_name="pending_admin_changes")
    op.drop_table("pending_admin_changes")
    op.drop_index(op.f("ix_alert_events_user_id"), table_name="alert_events")
    op.drop_table("alert_events")
    op.drop_index(op.f("ix_messages_user_id"), table_name="messages")
    op.drop_index("uq_messages_feishu_message_id", table_name="messages")
    op.drop_table("messages")
    op.drop_table("contacts")
    op.drop_table("email_templates")
    op.drop_table("app_settings")
    op.drop_table("users")
