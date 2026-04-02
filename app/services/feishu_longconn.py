import asyncio
import logging
import threading

import lark_oapi as lark
import lark_oapi.ws.client as lark_ws_client_module

from app.core.config import settings
from app.services.feishu_client import build_feishu_api_client, build_feishu_log_level
from app.services.feishu_message_service import FeishuMessageService

logger = logging.getLogger(__name__)

_client_thread: threading.Thread | None = None


def start_feishu_long_connection() -> None:
    global _client_thread

    if not settings.feishu_long_connection_enabled:
        logger.info("feishu long connection disabled")
        return

    if not settings.feishu_app_id or not settings.feishu_app_secret:
        logger.warning("feishu long connection not started because app credentials are missing")
        return

    if _client_thread is not None and _client_thread.is_alive():
        logger.info("feishu long connection already running")
        return

    _client_thread = threading.Thread(
        target=_run_long_connection_client,
        name="feishu-long-connection",
        daemon=True,
    )
    _client_thread.start()
    logger.info("feishu long connection thread started")


def _run_long_connection_client() -> None:
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        lark_ws_client_module.loop = loop

        message_service = FeishuMessageService(build_feishu_api_client())
        event_handler = (
            lark.EventDispatcherHandler.builder(
                settings.feishu_encrypt_key,
                settings.feishu_verification_token,
                build_feishu_log_level(),
            )
            .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(
                lambda _: _ignore_event("im.chat.access_event.bot_p2p_chat_entered_v1")
            )
            .register_p2_im_message_message_read_v1(
                lambda _: _ignore_event("im.message.message_read_v1")
            )
            .register_p2_im_message_receive_v1(message_service.handle_message_receive)
            .build()
        )
        ws_client = lark.ws.Client(
            app_id=settings.feishu_app_id,
            app_secret=settings.feishu_app_secret,
            log_level=build_feishu_log_level(),
            event_handler=event_handler,
            domain=settings.feishu_domain,
        )
        logger.info("starting feishu long connection client")
        ws_client.start()
    except Exception:
        logger.exception("feishu long connection client exited unexpectedly")


def _ignore_event(event_type: str) -> None:
    logger.debug("ignored feishu event: %s", event_type)
