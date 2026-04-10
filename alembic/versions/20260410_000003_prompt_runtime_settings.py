"""add prompt runtime settings

Revision ID: 20260410_000003
Revises: 20260402_000002
Create Date: 2026-04-10 11:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260410_000003"
down_revision = "20260402_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("chat_prompt_version", sa.String(length=64), nullable=False, server_default="chat_v2"),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "command_repair_prompt_version",
            sa.String(length=64),
            nullable=False,
            server_default="command_repair_v1",
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column("command_repair_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.alter_column("app_settings", "chat_prompt_version", server_default=None)
    op.alter_column("app_settings", "command_repair_prompt_version", server_default=None)
    op.alter_column("app_settings", "command_repair_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("app_settings", "command_repair_enabled")
    op.drop_column("app_settings", "command_repair_prompt_version")
    op.drop_column("app_settings", "chat_prompt_version")
