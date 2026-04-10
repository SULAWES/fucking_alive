from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    default_llm_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="openai")
    default_llm_model: Mapped[str] = mapped_column(String(128), nullable=False, default="gpt-4.1-mini")
    alert_default_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=72)
    chat_context_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    chat_prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="chat_v2")
    command_repair_prompt_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="command_repair_v1"
    )
    command_repair_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    admin_feishu_user_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
