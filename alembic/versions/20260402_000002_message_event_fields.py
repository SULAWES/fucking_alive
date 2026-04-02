"""add message event fields

Revision ID: 20260402_000002
Revises: 20260401_000001
Create Date: 2026-04-02 00:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260402_000002"
down_revision = "20260401_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("chat_id", sa.String(length=128), nullable=True))
    op.add_column("messages", sa.Column("chat_type", sa.String(length=32), nullable=True))
    op.add_column("messages", sa.Column("message_type", sa.String(length=32), nullable=True))
    op.add_column("messages", sa.Column("sender_user_id", sa.String(length=128), nullable=True))
    op.add_column("messages", sa.Column("sender_open_id", sa.String(length=128), nullable=True))
    op.add_column("messages", sa.Column("sender_union_id", sa.String(length=128), nullable=True))
    op.add_column(
        "messages",
        sa.Column("raw_event", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "raw_event")
    op.drop_column("messages", "sender_union_id")
    op.drop_column("messages", "sender_open_id")
    op.drop_column("messages", "sender_user_id")
    op.drop_column("messages", "message_type")
    op.drop_column("messages", "chat_type")
    op.drop_column("messages", "chat_id")
