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
    chat_prompt_version: str = "chat_v2"
    command_repair_prompt_version: str = "command_repair_v1"
    command_repair_enabled: bool = True
    alert_default_hours: int = 72
    alert_scan_interval_minutes: int = 10
    admin_feishu_user_id: str = ""
    admin_token: str = "change_me"
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""
    feishu_domain: str = "https://open.feishu.cn"
    feishu_long_connection_enabled: bool = False
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    alert_scheduler_enabled: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
