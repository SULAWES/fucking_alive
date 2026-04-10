import logging


LOG_CONTEXT_FIELDS = (
    "provider",
    "model",
    "scenario",
    "prompt_version",
    "user_id",
    "contact_id",
    "message_id",
    "chat_id",
    "event_type",
    "delivery_status",
    "latency_ms",
)


class ContextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        for field in LOG_CONTEXT_FIELDS:
            if not hasattr(record, field):
                setattr(record, field, "-")
        return super().format(record)


def configure_logging(log_level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        ContextFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s "
            "provider=%(provider)s model=%(model)s scenario=%(scenario)s prompt_version=%(prompt_version)s user_id=%(user_id)s "
            "contact_id=%(contact_id)s message_id=%(message_id)s chat_id=%(chat_id)s "
            "event_type=%(event_type)s delivery_status=%(delivery_status)s latency_ms=%(latency_ms)s"
        )
    )
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        handlers=[handler],
        force=True,
    )
