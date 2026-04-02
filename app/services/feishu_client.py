import lark_oapi as lark

from app.core.config import settings


def build_feishu_api_client() -> lark.Client:
    return (
        lark.Client.builder()
        .app_id(settings.feishu_app_id)
        .app_secret(settings.feishu_app_secret)
        .app_type(lark.AppType.SELF)
        .domain(settings.feishu_domain)
        .log_level(_build_log_level())
        .build()
    )


def build_feishu_log_level() -> lark.LogLevel:
    return _build_log_level()


def _build_log_level() -> lark.LogLevel:
    level = settings.log_level.upper()
    if level == "DEBUG":
        return lark.LogLevel.DEBUG
    if level == "WARNING":
        return lark.LogLevel.WARNING
    if level == "ERROR":
        return lark.LogLevel.ERROR
    return lark.LogLevel.INFO

