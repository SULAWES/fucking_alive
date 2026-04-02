import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    chat_id: Mapped[str | None] = mapped_column(String(128))
    chat_type: Mapped[str | None] = mapped_column(String(32))
    message_type: Mapped[str | None] = mapped_column(String(32))
    sender_user_id: Mapped[str | None] = mapped_column(String(128))
    sender_open_id: Mapped[str | None] = mapped_column(String(128))
    sender_union_id: Mapped[str | None] = mapped_column(String(128))
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    raw_event: Mapped[dict | None] = mapped_column(JSONB)
    feishu_message_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
