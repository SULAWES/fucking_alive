from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "alive-agent"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_timezone: str = "Asia/Shanghai"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://alive_agent:change_me@postgres:5432/alive_agent"
    default_llm_provider: str = "openai"
    default_llm_model: str = "gpt-4.1-mini"
    chat_context_messages: int = 10
    alert_default_hours: int = 72
    alert_scan_interval_minutes: int = 10
    admin_feishu_user_id: str = ""
    admin_token: str = "change_me"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
